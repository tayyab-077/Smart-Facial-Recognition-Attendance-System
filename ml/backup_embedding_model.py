#embeddin_model.py

import numpy as np
import cv2
import onnxruntime as ort
from pathlib import Path

class EmbeddingModel:
    def __init__(self, model_path=None):

        base_dir = Path(__file__).resolve().parents[1]

        if model_path is None:
            model_path = base_dir / "ml" / "models" / "arcface.onnx"

        self.model_path = str(model_path)

        # Load model safely
        try:
            self.session = ort.InferenceSession(
                self.model_path,
                providers=["CPUExecutionProvider"]
            )
        except Exception as e:
            raise RuntimeError(f"Error loading ONNX model: {e}")

        self.input_name = self.session.get_inputs()[0].name
        self.input_shape = self.session.get_inputs()[0].shape
        self.output_name = self.session.get_outputs()[0].name

    def preprocess(self, face_image: np.ndarray) -> np.ndarray:

        if face_image is None or face_image.size == 0:
            return None
        
        # Resize
        img = cv2.resize(face_image, (112, 112))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = img.astype("float32") / 255.0

        # (H,W,C) or (C,H,W)
        if self.input_shape[1] == 3:  # CHW
            img = np.transpose(img, (2, 0, 1))

        img = np.expand_dims(img, axis=0)
        return img

    def get_embedding(self, face_image: np.ndarray) -> np.ndarray:

        input_blob = self.preprocess(face_image)
        if input_blob is None:
            return None

        try:
            result = self.session.run(
                [self.output_name],
                {self.input_name: input_blob}
            )
        except Exception:
            return None

        embedding = np.array(result[0][0])

        # Normalize
        norm = np.linalg.norm(embedding)
        if norm == 0:
            return None

        return embedding / norm
