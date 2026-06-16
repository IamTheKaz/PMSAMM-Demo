#!/usr/bin/env python3
"""Serve a local HTML upload page and run sam_model.tflite inference on uploaded images."""

import cgi
import io
import json
import mimetypes
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

try:
    import numpy as np
    from PIL import Image
except ImportError as e:
    raise SystemExit(
        "Missing dependency: install with `python3 -m pip install numpy pillow tensorflow`"
    ) from e

MODEL_PATH = Path(__file__).resolve().parent / "sam_model.tflite"
PORT = 8000
CLASS_LABELS = {
    0: "none",
    1: "underextrusion",
    2: "stringing",
    3: "spaghetti",
}
IMAGE_SIZE = (224, 224)


def load_interpreter():
    Interpreter = None
    try:
        import tensorflow as tf
        Interpreter = tf.lite.Interpreter
        print("Using tensorflow.lite.Interpreter via tf.lite")
    except Exception as e1:
        try:
            from tensorflow.lite import Interpreter as DirectInterpreter
            Interpreter = DirectInterpreter
            print("Using tensorflow.lite.Interpreter direct")
        except Exception as e2:
            try:
                from tflite_runtime.interpreter import Interpreter as TFLiteRuntimeInterpreter
                Interpreter = TFLiteRuntimeInterpreter
                print("Using tflite_runtime.Interpreter")
            except Exception as e3:
                print("TensorFlow Lite interpreter import failed.")
                print("Python executable:", sys.executable)
                print("Python version:", sys.version)
                print("sys.path:", sys.path)
                print("tensorflow import error:", repr(e1))
                print("tensorflow.lite import error:", repr(e2))
                print("tflite_runtime import error:", repr(e3))
                raise RuntimeError(
                    "TensorFlow Lite interpreter not found. Install tensorflow or tflite-runtime."
                ) from e3

    interpreter = Interpreter(model_path=str(MODEL_PATH))
    interpreter.allocate_tensors()
    return interpreter


def preprocess_image(image_bytes):
    img = Image.open(image_bytes).convert("RGB")
    img = img.resize(IMAGE_SIZE, Image.BILINEAR)
    arr = np.array(img, dtype=np.float32) / 255.0
    arr = np.expand_dims(arr, axis=0)
    return arr


def dequantize_output(output, output_details):
    scale, zero_point = output_details["quantization"]
    if scale and zero_point is not None:
        return (output.astype(np.float32) - zero_point) * scale
    return output.astype(np.float32)


class InferenceHandler(BaseHTTPRequestHandler):
    interpreter = None
    input_details = None
    output_details = None

    def do_GET(self):
        if self.path in ["/", "/simple_local_server_sam.html"]:
            self.serve_file(Path(__file__).resolve().parent / "simple_local_server_sam.html", "text/html; charset=utf-8")
            return

        if self.path == "/__ping__":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "server": "local_sam_server"}).encode("utf-8"))
            return

        if self.path == "/favicon.ico":
            self.send_error(404, "Not Found")
            return

        local_path = Path(__file__).resolve().parent / self.path.lstrip("/")
        if local_path.exists() and local_path.is_file():
            self.serve_file(local_path)
            return

        self.send_error(404, "Not Found")

    def serve_file(self, path, content_type=None):
        data = path.read_bytes()
        content_type = content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path != "/predict":
            self.send_error(404, "Not Found")
            return

        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self.send_error(400, "Expected multipart form data")
            return

        length = int(self.headers.get("Content-Length", 0))
        environ = {
            'REQUEST_METHOD': 'POST',
            'CONTENT_TYPE': self.headers.get('Content-Type', ''),
            'CONTENT_LENGTH': str(length),
        }
        fs = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ=environ)
        if 'image' not in fs:
            self.send_error(400, 'Missing image field')
            return

        file_item = fs['image']
        if not file_item.file:
            self.send_error(400, 'Image file missing')
            return

        image_bytes = file_item.file.read()

        try:
            output = self.run_inference(image_bytes)
            response = {
                "label": output["label"],
                "confidence": output["confidence"],
                "raw_scores": output["raw_scores"],
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode("utf-8"))
        except Exception as exc:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))

    def run_inference(self, image_bytes):
        if self.interpreter is None:
            self.interpreter = load_interpreter()
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()[0]

        image = preprocess_image(io.BytesIO(image_bytes))
        self.interpreter.set_tensor(self.input_details[0]["index"], image.astype(self.input_details[0]["dtype"]))
        self.interpreter.invoke()
        raw_output = self.interpreter.get_tensor(self.output_details["index"])[0]
        output = dequantize_output(raw_output, self.output_details)
        predicted_idx = int(np.argmax(output))
        confidence = float(output[predicted_idx]) * 100
        label = CLASS_LABELS.get(predicted_idx, "unknown")
        raw_scores = {CLASS_LABELS.get(i, str(i)): float(output[i]) * 100.0 for i in range(len(output))}
        return {
            "label": label,
            "confidence": round(confidence, 1),
            "raw_scores": raw_scores,
        }

    def log_message(self, format, *args):
        sys.stdout.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format % args))


def run_server():
    if not MODEL_PATH.exists():
        raise SystemExit(f"Model file not found at {MODEL_PATH}")

    os.chdir(os.path.dirname(__file__))
    server = HTTPServer(("", PORT), InferenceHandler)
    print(f"Serving on http://localhost:{PORT}")
    print("Upload images at http://localhost:8000/simple_local_server_sam.html")
    server.serve_forever()


if __name__ == "__main__":
    import io
    run_server()
