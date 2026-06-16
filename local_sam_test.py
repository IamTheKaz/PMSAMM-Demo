#!/usr/bin/env python3
"""Run local inference on sam_model.tflite and print each class confidence."""

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

MODEL_FILE = Path(__file__).parent / "sam_model.tflite"
CLASS_LABELS = {
    0: "none",
    1: "underextrusion",
    2: "stringing",
    3: "spaghetti",
}
IMAGE_SIZE = (224, 224)


def load_interpreter(model_path: Path):
    try:
        from tflite_runtime.interpreter import Interpreter
    except ImportError:
        try:
            from tensorflow.lite import Interpreter
        except ImportError as exc:
            raise ImportError(
                "Install tflite_runtime or tensorflow to run this script.\n"
                "Example: python3 -m pip install pillow numpy tflite-runtime"
            ) from exc

    interpreter = Interpreter(model_path=str(model_path))
    interpreter.allocate_tensors()
    return interpreter


def preprocess_image(image_path: Path, input_details):
    img = Image.open(image_path).convert("RGB")
    img = img.resize(IMAGE_SIZE, Image.BILINEAR)
    array = np.array(img, dtype=np.float32) / 255.0

    if input_details[0]["dtype"] == np.uint8:
        array = (array * 255.0).astype(np.uint8)
    elif input_details[0]["dtype"] == np.int8:
        scale, zero_point = input_details[0]["quantization"]
        if scale != 0:
            array = (array / scale + zero_point).astype(np.int8)
        else:
            array = array.astype(np.int8)
    else:
        array = array.astype(input_details[0]["dtype"])

    return np.expand_dims(array, axis=0)


def dequantize_output(output, output_details):
    scale, zero_point = output_details["quantization"]
    if scale and zero_point is not None:
        return (output.astype(np.float32) - zero_point) * scale
    return output.astype(np.float32)


def run_one_image(interpreter, image_path: Path):
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()[0]

    input_data = preprocess_image(image_path, input_details)
    interpreter.set_tensor(input_details[0]["index"], input_data)
    interpreter.invoke()

    output = interpreter.get_tensor(output_details["index"])[0]
    output = dequantize_output(output, output_details)

    return output


def format_results(output):
    scores = {
        CLASS_LABELS.get(i, str(i)): float(output[i]) * 100.0
        for i in range(len(output))
    }
    sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return sorted_scores


def main():
    parser = argparse.ArgumentParser(
        description="Run local SAM TFLite inference and print class confidences."
    )
    parser.add_argument("paths", nargs="+", help="Image file(s) or directory(ies) to evaluate.")
    args = parser.parse_args()

    if not MODEL_FILE.exists():
        print(f"Error: model file not found at {MODEL_FILE}")
        sys.exit(1)

    interpreter = load_interpreter(MODEL_FILE)

    image_paths = []
    for path_str in args.paths:
        path = Path(path_str)
        if path.is_dir():
            image_paths.extend(sorted([p for p in path.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".gif"}]))
        elif path.is_file():
            image_paths.append(path)
        else:
            print(f"Warning: path not found: {path}")

    if not image_paths:
        print("No image files found. Provide a file path or directory containing images.")
        sys.exit(1)

    for image_path in image_paths:
        print(f"\nImage: {image_path}")
        output = run_one_image(interpreter, image_path)
        results = format_results(output)
        for label, score in results:
            print(f"  {label:<16} {score:6.2f}%")
        top_label, top_score = results[0]
        print(f"  -> predicted: {top_label} ({top_score:.2f}%)")


if __name__ == "__main__":
    main()
