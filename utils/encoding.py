# utils/encoding.py
# Base64 helpers for incoming images (used by enroll & recognize endpoints).


import base64
import numpy as np
import cv2

def b64_to_cv2(img_b64: str):
    """
    Accepts dataurl or raw base64. Returns BGR cv2 image or None.
    """
    if not img_b64:
        return None
    header, body = (img_b64.split(",", 1) + [""])[:2]
    try:
        data = base64.b64decode(body or header)
    except Exception:
        return None
    nparr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return img
