# Local SAM Model Testing

Use this repository's `sam_model.tflite` locally without AWS.

## Requirements

- Python 3.8+
- `pip` installed

Install dependencies:

```bash
python3 -m pip install pillow numpy
```

Then install either `tflite-runtime` or `tensorflow`:

```bash
python3 -m pip install tflite-runtime
```

If that package is not available on your platform, install TensorFlow instead:

```bash
python3 -m pip install tensorflow
```

## Run local inference

From the repository folder:

```bash
python3 local_sam_test.py path/to/image.jpg
```

Or evaluate all images in a directory:

```bash
python3 local_sam_test.py ./test_images
```

## Output

The script prints:

- each class label
- confidence for each class
- the top predicted label

This gives you a quick way to test the model locally without going through AWS or Lambda.
