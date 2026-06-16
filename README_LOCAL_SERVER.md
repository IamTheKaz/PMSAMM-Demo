# Local SAM Model Server

This project includes a simple local Python server to test `sam_model.tflite` from the browser without AWS.

## Setup

1. Open a terminal in the project folder:

```bash
cd '/Users/kaz/Desktop/School/ARIN/ARIN 495/PMSAMM-Demo'
```

2. Install dependencies if needed:

```bash
python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install numpy pillow tensorflow
```

If `tensorflow` is too large or fails to install, install TensorFlow Lite runtime instead:

```bash
python3 -m pip install tflite-runtime
```

To verify you are using the same Python interpreter for both server and install, run:

```bash
python3 -c "import sys; print(sys.executable); import tensorflow as tf; print(tf.__version__)"
```

If that fails, use the Python executable shown there when starting the server.

3. Start the server:

```bash
python3 local_sam_server.py
```

> Do not use `python3 -m http.server`, because that server cannot handle `/predict` POST requests.
> If you previously started another local server on port 8000, stop it first.

4. Open the test page in your browser:

```text
http://localhost:8000/simple_local_server_sam.html
```

## What it does

- Serves `simple_local_server_sam.html` from `localhost:8000`
- Accepts image uploads at `/predict`
- Runs inference with `sam_model.tflite` on the local Python server
- Returns per-class confidences and top prediction

## Notes

- Make sure `sam_model.tflite` is present in the same folder as `local_sam_server.py`.
- This avoids AWS entirely and uses local Python/TensorFlow.
