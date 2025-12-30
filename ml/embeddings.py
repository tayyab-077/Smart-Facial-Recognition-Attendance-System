# ml/embeddings.py
# Handles loading the ONNX embedding model (EmbeddingModel)
# and provides helper functions for computing embeddings
# from images or folders.

# ---------------------------------------------
# Loads ArcFace/MobileFaceNet and returns embeddings
# Expects: 112x112 aligned BGR input (from align_face)
# ONNX model expects NHWC
# ---------------------------------------------

import cv2
import numpy as np
import onnxruntime as ort
from pathlib import Path


class EmbeddingModel:
    def __init__(self, model_name="arcface.onnx"):
        base_dir = Path(__file__).resolve().parents[1]
        model_path = base_dir / "ml" / "models" / model_name

        if not model_path.exists():
            raise FileNotFoundError(f"Embedding model not found: {model_path}")

        self.session = ort.InferenceSession(
            str(model_path),
            providers=["CPUExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name

        # 🔍 Debug once (optional)
        print("Embedding model input shape:", self.session.get_inputs()[0].shape)

    def preprocess(self, face):
        """
        face: 112x112 BGR aligned
        output: NHWC float32 normalized
        """

        face = cv2.resize(face, (112, 112))
        face = cv2.cvtColor(face, cv2.COLOR_BGR2RGB)

        face = face.astype(np.float32)
        face = (face - 127.5) / 128.0   # ArcFace standard [-1, 1]

        # ✅ KEEP NHWC
        face = np.expand_dims(face, axis=0)  # (1, 112, 112, 3)

        return face

    def get_embedding(self, face):
        try:
            inp = self.preprocess(face)

            emb = self.session.run(
                None,
                {self.input_name: inp}
            )[0]

            emb = emb.flatten()

            # L2-normalize → important for matching
            norm = np.linalg.norm(emb)
            if norm == 0:
                return None

            return emb / norm

        except Exception as e:
            print("Embedding error:", e)
            return None


# Used by the API
def get_embedding_model():
    return EmbeddingModel("arcface.onnx")


# ------------------------------------------------------
# Compute mean embedding for a folder of aligned images
# ------------------------------------------------------
def compute_folder_embedding(folder_path):
    """
    folder_path: str, path to folder containing face images
    Returns:
        mean embedding (np.ndarray of shape (512,))
        OR None if failed
    """
    import os
    from ml.face_align import align_face
    from ml.scrfd_detector import SCRFDDetector

    model = get_embedding_model()
    detector = SCRFDDetector()

    embeddings = []

    for file in sorted(os.listdir(folder_path)):
        if not file.lower().endswith((".jpg", ".png", ".jpeg")):
            continue

        path = os.path.join(folder_path, file)
        img = cv2.imread(path)
        if img is None:
            continue

        faces = detector.detect(img, conf_threshold=0.45)
        if len(faces) == 0:
            continue

        best = max(faces, key=lambda x: x["score"])
        kps = best["kps"]

        try:
            aligned = align_face(img, kps)
            print("Aligned shape:", aligned.shape)
        except:
            continue

        emb = model.get_embedding(aligned)
        if emb is None:
            continue

        embeddings.append(emb)

    # if len(embeddings) == 0:
    #     return None
    
    
    # ----------------------------------
    # 🔑 QUALITY GATE (VERY IMPORTANT)
    # ----------------------------------
    MIN_VALID_FACES = 2

    if len(embeddings) < MIN_VALID_FACES:
        print(f"❌ Not enough good faces for embedding: {len(embeddings)} found")
        return None

    emb_mat = np.vstack(embeddings)
    mean_emb = emb_mat.mean(axis=0)

    # normalize again
    return mean_emb / (np.linalg.norm(mean_emb) + 1e-6)
