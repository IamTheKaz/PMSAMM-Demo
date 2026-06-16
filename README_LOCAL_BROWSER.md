# Local Browser SAM TFLite Test

This page lets you test `sam_model.tflite` entirely in your browser, with no AWS required.

## Setup

1. Make sure `sam_model.tflite` is in the same folder as `simple_local_sam.html`.
2. Start a simple local web server from the project folder:

```bash
cd '/Users/kaz/Desktop/School/ARIN/ARIN 495/PMSAMM-Demo'
python3 -m http.server 8000
```

3. Open the page in your browser:

```text
http://localhost:8000/simple_local_sam.html
```

## How to use

- Choose an image file from your computer.
- Click `Run model`.
- The page will show each class confidence and the top prediction.

## Notes

- This runs `sam_model.tflite` locally in the browser using TensorFlow.js TFLite.
- You do not need AWS, Lambda, or Python packages for the browser page itself.
- If the model fails to load, make sure you are serving the page over HTTP and that `sam_model.tflite` exists in the same folder.
