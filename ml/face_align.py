# ml/face_align.py
# -----------------------------
# Align face based on SCRFD 5 keypoints
# Output: 112x112 aligned face (ArcFace standard)
# -----------------------------
    
import cv2
import numpy as np

# Standard ArcFace template points
ARC_FACE_TEMPLATE = np.array([
    [38.2946, 51.6963],   # left eye
    [73.5318, 51.5014],   # right eye
    [56.0252, 71.7366],   # nose
    [41.5493, 92.3655],   # left mouth
    [70.7299, 92.2041]    # right mouth
], dtype=np.float32)

def align_face(img, kps, output_size=(112, 112)):
    """
    img : original BGR image
    kps : list of five (x, y) facial landmarks from SCRFD
    returns aligned BGR image (112x112)
    """

    if len(kps) != 5:
        raise ValueError("SCRFD landmarks must have exactly 5 points")

    # Convert to float32
    src_pts = np.array(kps, dtype=np.float32)

    # Destination template
    dst_pts = ARC_FACE_TEMPLATE.copy()

    # Estimate transformation matrix
    transform = cv2.estimateAffinePartial2D(src_pts, dst_pts, method=cv2.LMEDS)[0]
    if transform is None:
        raise ValueError("Could not estimate affine transform for alignment")

    # Apply warp
    aligned = cv2.warpAffine(
        img,
        transform,
        output_size,
        borderValue=0
    )

    return aligned
