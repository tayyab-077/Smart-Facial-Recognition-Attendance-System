from pathlib import Path
import onnxruntime as ort
import numpy as np
import cv2

# Correct base directory
BASE_DIR = Path(__file__).resolve().parents[1]  # this points to VisionAttendance/ml
MODEL_PATH = BASE_DIR / "models" / "scrfd_2.5g_bnkps.onnx"
TEST_IMAGE = BASE_DIR / "tests" / "test.jpg"

print("Model path:", MODEL_PATH)
print("Test image:", TEST_IMAGE)

# Load model
session = ort.InferenceSession(str(MODEL_PATH), providers=["CPUExecutionProvider"])

# Load test image
img = cv2.imread(str(TEST_IMAGE))
if img is None:
    raise FileNotFoundError("❌ test.jpg not found or unreadable!")

# Preprocess
input_img = cv2.resize(img, (640, 640))
input_img = input_img[:, :, ::-1]
input_img = np.expand_dims(np.transpose(input_img, (2, 0, 1)), 0).astype(np.float32)

# Run inference
outputs = session.run(None, {"input.1": input_img})
print("SCRFD Output Shapes:")
for out in outputs:
    print(np.array(out).shape)
