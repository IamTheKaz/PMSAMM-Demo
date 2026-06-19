import base64
import io
import importlib.util
import json
import os
from pathlib import Path
import sys
import traceback

import numpy as np
from PIL import Image

DEFAULT_MODEL_PATH = "/var/task/sam_model.tflite"
MODEL_CANDIDATES = [
    DEFAULT_MODEL_PATH,
    "/opt/sam_model.tflite",
    "/opt/python/sam_model.tflite",
]
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
_BACKEND_NAME = None
_MODEL_PATH = None


def bootstrap_layer_paths():
    # Code-only fallback: include common Lambda layer package paths if present.
    prefixes = ["/opt/python", "/opt/python/lib"]
    for prefix in prefixes:
        if os.path.isdir(prefix) and prefix not in sys.path:
            sys.path.append(prefix)

    lib_root = "/opt/python/lib"
    if os.path.isdir(lib_root):
        for child in os.listdir(lib_root):
            candidate = os.path.join(lib_root, child, "site-packages")
            if os.path.isdir(candidate) and candidate not in sys.path:
                sys.path.append(candidate)


def resolve_model_path():
    env_model = os.environ.get("MODEL_PATH")
    candidates = [env_model] + MODEL_CANDIDATES if env_model else MODEL_CANDIDATES
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return Path(candidate)
    return Path(candidates[0])


def respond(status_code, body):
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body),
    }


def load_interpreter():
    global _INTERPRETER, _INPUT_DETAILS, _OUTPUT_DETAILS, _BACKEND_NAME, _MODEL_PATH
    if _INTERPRETER is not None:
        print(f"Reusing cached interpreter via {_BACKEND_NAME}")
        return _INTERPRETER, _INPUT_DETAILS, _OUTPUT_DETAILS

    bootstrap_layer_paths()

    interpreter_cls = None
    try:
        from tflite_runtime.interpreter import Interpreter as TFLiteInterpreter

        interpreter_cls = TFLiteInterpreter
        _BACKEND_NAME = "tflite_runtime"
    except Exception:
        try:
            import tensorflow as tf

            interpreter_cls = tf.lite.Interpreter
            _BACKEND_NAME = "tensorflow"
        except Exception as exc:
            raise RuntimeError(
                "No TensorFlow Lite interpreter available. Package tflite-runtime or tensorflow with the Lambda."
            ) from exc

    _MODEL_PATH = resolve_model_path()
    if not _MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model file not found. Tried: {', '.join([p for p in [os.environ.get('MODEL_PATH')] + MODEL_CANDIDATES if p])}"
        )

    print(f"Loading TFLite model from {_MODEL_PATH} using {_BACKEND_NAME}")
    _INTERPRETER = interpreter_cls(model_path=str(_MODEL_PATH))
    _INTERPRETER.allocate_tensors()
    _INPUT_DETAILS = _INTERPRETER.get_input_details()[0]
    _OUTPUT_DETAILS = _INTERPRETER.get_output_details()[0]
    print(
        "Interpreter ready:",
        json.dumps(
            {
                "input_shape": _INPUT_DETAILS.get("shape", []).tolist()
                if hasattr(_INPUT_DETAILS.get("shape", []), "tolist")
                else _INPUT_DETAILS.get("shape", []),
                "input_dtype": str(_INPUT_DETAILS.get("dtype")),
                "output_dtype": str(_OUTPUT_DETAILS.get("dtype")),
                "quantization": _OUTPUT_DETAILS.get("quantization", (0.0, 0)),
            }
        ),
    )
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
    print(f"Decoded image size: {image.size}")
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

    print(
        "SAM inference result:",
        json.dumps(
            {
                "label": CLASS_LABELS.get(predicted_index, "unknown"),
                "confidence": round(confidence, 1),
                "raw_scores": raw_scores,
            }
        ),
    )

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
    request_id = getattr(context, "aws_request_id", "unknown")
    method = (
        event.get("requestContext", {})
        .get("http", {})
        .get("method", event.get("httpMethod", "POST"))
    )
    print(
        "SAM request received:",
        json.dumps(
            {
                "request_id": request_id,
                "method": method,
                "has_body": bool(event.get("body")),
                "is_base64_encoded": bool(event.get("isBase64Encoded")),
                "configured_model_path": os.environ.get("MODEL_PATH", DEFAULT_MODEL_PATH),
            }
        ),
    )

    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    try:
        body = parse_event_body(event)
    except Exception as exc:
        return respond(400, {"error": f"Bad request body: {exc}"})

    if body.get("action") == "ping":
        print(f"SAM ping request handled for {request_id}")
        return respond(200, {"status": "ok", "model_path": str(resolve_model_path())})

    if body.get("action") == "diag":
        print(f"SAM diagnostic request handled for {request_id}")
        return respond(
            200,
            {
                "status": "diag",
                "python_version": sys.version,
                "executable": sys.executable,
                "cwd": os.getcwd(),
                "model_path": str(resolve_model_path()),
                "model_exists": resolve_model_path().exists(),
                "model_candidates": [p for p in [os.environ.get("MODEL_PATH")] + MODEL_CANDIDATES if p],
                "has_tflite_runtime": bool(importlib.util.find_spec("tflite_runtime")),
                "has_tensorflow": bool(importlib.util.find_spec("tensorflow")),
                "has_numpy": bool(importlib.util.find_spec("numpy")),
                "has_pillow": bool(importlib.util.find_spec("PIL")),
                "sys_path": sys.path,
            },
        )

    try:
        image_bytes = decode_image_field(body.get("image"))
        print(f"Decoded image payload bytes: {len(image_bytes)}")
        result = run_inference(image_bytes)
        return respond(200, result)
    except Exception as exc:
        print(f"SAM inference failed for {request_id}: {exc}")
        print(traceback.format_exc())
        return respond(500, {"error": str(exc)})
