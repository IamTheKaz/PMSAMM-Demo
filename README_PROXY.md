# Local Proxy for SAM Lambda Testing

This repository includes a small local proxy so you can test the SAM Lambda from `simple_sam_inference.html` without CORS issues.

## How to run

1. Open a terminal in the project folder:

```bash
cd '/Users/kaz/Desktop/School/ARIN/ARIN 495/PMSAMM-Demo'
```

2. Start the proxy server:

```bash
python3 local_proxy.py
```

3. Open the page in your browser:

```text
http://localhost:8000/simple_sam_inference.html
```

4. Upload an image and click `Run Model`.

## What it does

- Serves `simple_sam_inference.html` from `localhost:8000`
- Proxies requests from `/infer` to the AWS SAM Lambda URL
- Returns the Lambda response without browser CORS issues

## Notes

- No extra Python packages are required for the proxy.
- The model still runs in AWS Lambda; this just makes local browser testing work.
