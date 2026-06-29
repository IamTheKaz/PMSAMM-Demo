# ================================================================
# SAM PRINT DEFECT INFERENCE - Haven-1 3D Printer Defect Detection
# ================================================================
# AWS Lambda function for running SAM (System for Additive Manufacturing)
# inference on 3D print images. Uses TensorFlow Lite for edge inference.
#
# Purpose: Classify 3D print defects (underextrusion, stringing, spaghetti)
#          with confidence scoring. Part of Haven-1 monitoring pipeline.
# ================================================================

import json
import base64
import urllib.request
import numpy as np
from PIL import Image
import io
import os
from ai_edge_litert.interpreter import Interpreter

# ================================================================
# MODEL CONFIGURATION
# ================================================================
# GitHub hosted model URL for remote deployment
MODEL_URL = "https://raw.githubusercontent.com/IamTheKaz/PMSAMM-Demo/main/sam_model.tflite"
# Local cache path for Lambda /tmp storage
MODEL_PATH = "/tmp/sam_model.tflite"

# ================================================================
# DEFECT CLASS LABELS
# ================================================================
# SAM model output class mapping
# 0: No defect detected
# 1: Underextrusion (insufficient filament flow)
# 2: Stringing (thin filament strands between parts)
# 3: Spaghetti (catastrophic filament tangle)
CLASS_LABELS = {
    0: "none",
    1: "underextrusion",
    2: "stringing",
    3: "spaghetti"
}

# ================================================================
# INFERENCE PARAMETERS
# ================================================================
# SAM (System for Additive Manufacturing) model expects 224x224 RGB images
IMAGE_SIZE = (224, 224)

# Global TensorFlow Lite interpreter instance (cached for performance)
_interpreter = None


# ================================================================
# MODEL LOADING AND INITIALIZATION
# ================================================================
def get_interpreter():
    """
    Initialize and cache TensorFlow Lite interpreter.
    
    Downloads model from GitHub on first invocation if not cached locally.
    Allocates input/output tensors for inference.
    
    Returns:
        ai_edge_litert.interpreter.Interpreter: Initialized model interpreter
    """
    global _interpreter
    if _interpreter is None:
        # Download model if not already cached in /tmp
        if not os.path.exists(MODEL_PATH):
            print("Downloading model from GitHub...")
            urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
            print("Model downloaded.")
        
        # Initialize TensorFlow Lite interpreter
        _interpreter = Interpreter(model_path=MODEL_PATH)
        # Allocate tensors for input and output
        _interpreter.allocate_tensors()
    return _interpreter


# ================================================================
# IMAGE PREPROCESSING
# ================================================================
def preprocess_image(image_b64):
    """
    Preprocess base64-encoded image for SAM (System for Additive Manufacturing) inference.
    
    Pipeline:
    1. Decode base64 (handles data URL prefix)
    2. Load as PIL Image
    3. Convert to RGB
    4. Resize to 224x224
    5. Normalize to [0, 1] float32
    6. Add batch dimension (1, 224, 224, 3)
    
    Args:
        image_b64 (str): Base64 encoded image or data URL
        
    Returns:
        np.ndarray: Preprocessed image array (1, 224, 224, 3)
    """
    # Handle data URL format (remove "data:image/jpeg;base64," prefix)
    if "," in image_b64:
        image_b64 = image_b64.split(",", 1)[1]
    
    # Decode base64 to bytes and open as PIL Image
    image_bytes = base64.b64decode(image_b64)
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    
    # Resize to model input size
    img = img.resize(IMAGE_SIZE)
    
    # Convert to normalized float32 array [0, 1]
    arr = np.array(img, dtype=np.float32) / 255.0
    
    # Add batch dimension for inference
    arr = np.expand_dims(arr, axis=0)
    return arr


# ================================================================
# LAMBDA HANDLER - Main Entry Point
# ================================================================
def lambda_handler(event, context):
    """
    AWS Lambda handler for SAM (System for Additive Manufacturing) defect inference.
    
    Accepts base64-encoded image, runs SAM inference,
    returns defect classification with confidence score.
    
    Args:
        event: API Gateway Lambda event containing JSON body with image
        context: Lambda context
        
    Returns:
        dict: API Gateway formatted response with label, confidence, raw scores
    """
    # ================================================================
    # PARSE REQUEST
    # ================================================================
    try:
        raw_body = event.get("body", "{}")
        if event.get("isBase64Encoded", False):
            raw_body = base64.b64decode(raw_body).decode("utf-8")
        body = json.loads(raw_body)
    except Exception as e:
        return {"statusCode": 400, "body": json.dumps({"error": "Bad request: " + str(e)})}

    # Extract base64 image from request
    image_b64 = body.get("image", None)
    if not image_b64:
        return {"statusCode": 400, "body": json.dumps({"error": "No image provided"})}

    # ================================================================
    # RUN INFERENCE
    # ================================================================
    try:
        # Get cached interpreter instance
        interpreter = get_interpreter()
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()

        # Preprocess image to model input format
        input_data = preprocess_image(image_b64)

        # Run TensorFlow Lite inference
        interpreter.set_tensor(input_details[0]["index"], input_data)
        interpreter.invoke()
        
        # Extract output probabilities
        output = interpreter.get_tensor(output_details[0]["index"])[0]

        # ================================================================
        # POST-PROCESS RESULTS
        # ================================================================
        # Find predicted class (highest probability)
        predicted_idx = int(np.argmax(output))
        confidence = float(output[predicted_idx]) * 100

        # Get human-readable label
        label = CLASS_LABELS.get(predicted_idx, "unknown")

        # If confidence below 55%, defer to visual inspection
        if confidence < 55:
            label = "low confidence (unsure)"

        # Log inference result
        print(f"SAM (System for Additive Manufacturing) result: label={label}, confidence={confidence:.1f}, raw={output.tolist()}")

        # ================================================================
        # RETURN RESPONSE
        # ================================================================
        return {
            "statusCode": 200,
            "body": json.dumps({
                "label": label,
                "confidence": round(confidence, 1),
                "raw_scores": {CLASS_LABELS.get(i, str(i)): round(float(s)*100, 1) for i, s in enumerate(output)}
            })
        }

    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
