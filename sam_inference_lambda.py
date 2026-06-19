import base64
import io
import json
import os
from pathlib import Path

import numpy as np
from PIL import Image

MODEL_PATH = Path(os.environ.get("MODEL_PATH", "/var/task/sam_model.tflite"))
IMAGE_SIZE = (224, 224)
CLASS_LABELS = {
    0: "none",
    1: "underextrusion",
    2: "stringing",
    3: "spaghetti",
}
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
}

_INTERPRETER = None
_INPUT_DETAILS = None
_OUTPUT_DETAILS = None


def respond(status_code, body):
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body),
    }


def load_interpreter():
    global _INTERPRETER, _INPUT_DETAILS, _OUTPUT_DETAILS
    if _INTERPRETER is not None:
        return _INTERPRETER, _INPUT_DETAILS, _OUTPUT_DETAILS

    interpreter_cls = None
    try:
        from tflite_runtime.interpreter import Interpreter as TFLiteInterpreter

        interpreter_cls = TFLiteInterpreter
    except Exception:
        try:
            import tensorflow as tf

            interpreter_cls = tf.lite.Interpreter
        except Exception as exc:
            raise RuntimeError(
                "No TensorFlow Lite interpreter available. Package tflite-runtime or tensorflow with the Lambda."
            ) from exc

    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model file not found at {MODEL_PATH}")

    _INTERPRETER = interpreter_cls(model_path=str(MODEL_PATH))
    _INTERPRETER.allocate_tensors()
    _INPUT_DETAILS = _INTERPRETER.get_input_details()[0]
    _OUTPUT_DETAILS = _INTERPRETER.get_output_details()[0]
    return _INTERPRETER, _INPUT_DETAILS, _OUTPUT_DETAILS


def decode_image_field(image_value):
    if not image_value:
        raise ValueError("Missing image field")

    if isinstance(image_value, str) and image_value.startswith("data:"):
        try:
            _, encoded = image_value.split(",", 1)
        except ValueError as exc:
            raise ValueError("Malformed image data URL") from exc
        return base64.b64decode(encoded)

    if isinstance(image_value, str):
        return base64.b64decode(image_value)

    raise ValueError("Unsupported image payload format")


def preprocess_image(image_bytes):
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    image = image.resize(IMAGE_SIZE, Image.BILINEAR)
    array = np.array(image, dtype=np.float32) / 255.0
    return np.expand_dims(array, axis=0)


def dequantize_output(output_tensor, output_details):
    scale, zero_point = output_details.get("quantization", (0.0, 0))
    if scale:
        return (output_tensor.astype(np.float32) - zero_point) * scale
    return output_tensor.astype(np.float32)


def run_inference(image_bytes):
    interpreter, input_details, output_details = load_interpreter()
    input_array = preprocess_image(image_bytes).astype(input_details["dtype"])
    interpreter.set_tensor(input_details["index"], input_array)
    interpreter.invoke()
    raw_output = interpreter.get_tensor(output_details["index"])[0]
    scores = dequantize_output(raw_output, output_details)

    predicted_index = int(np.argmax(scores))
    confidence = float(scores[predicted_index]) * 100.0
    raw_scores = {
        CLASS_LABELS.get(i, str(i)): round(float(scores[i]) * 100.0, 2)
        for i in range(len(scores))
    }

    return {
        "label": CLASS_LABELS.get(predicted_index, "unknown"),
        "confidence": round(confidence, 1),
        "raw_scores": raw_scores,
    }


def parse_event_body(event):
    raw_body = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        raw_body = base64.b64decode(raw_body).decode("utf-8")
    if isinstance(raw_body, str):
        return json.loads(raw_body)
    if isinstance(raw_body, dict):
        return raw_body
    raise ValueError("Unsupported request body")


def lambda_handler(event, context):
    method = (
        event.get("requestContext", {})
        .get("http", {})
        .get("method", event.get("httpMethod", "POST"))
    )

    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    try:
        body = parse_event_body(event)
    except Exception as exc:
        return respond(400, {"error": f"Bad request body: {exc}"})

    if body.get("action") == "ping":
        return respond(200, {"status": "ok", "model_path": str(MODEL_PATH)})

    try:
        image_bytes = decode_image_field(body.get("image"))
        result = run_inference(image_bytes)
        return respond(200, result)
    except Exception as exc:
        return respond(500, {"error": str(exc)})
