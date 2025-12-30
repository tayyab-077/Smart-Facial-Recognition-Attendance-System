# ml/processor.py
# ---------------------------------------------------------
# Finalizes pending enrollment:
#   - moves pending images → dataset/<name>
#   - detects faces + aligns each face
#   - computes embedding for each face (ArcFace 112x112)
#   - averages all embeddings → final per-user embedding
#   - inserts user + embedding into DB
# ---------------------------------------------------------

from pathlib import Path
import shutil
import json
import numpy as np
import cv2
import time

from database.db import db_conn
from utils.file_utils import sanitize_name, ensure_dir, remove_dir
from ml.embeddings import EmbeddingModel
from ml.scrfd_detector import SCRFDDetector
from ml.face_align import align_face

BASE_DIR = Path(__file__).resolve().parents[1]
PENDING_DIR = BASE_DIR / "storage" / "pending"
DATASET_DIR = BASE_DIR / "storage" / "dataset"

# ---------------------------------------------
# Compute embedding for a folder of images
# ---------------------------------------------
def compute_folder_embedding(folder_path: str):
    model = EmbeddingModel()                 # ArcFace ONNX
    detector = SCRFDDetector()               # SCRFD face detector

    embeddings = []

    for img_path in sorted(Path(folder_path).glob("*.jpg")):
        img = cv2.imread(str(img_path))
        if img is None:
            continue

        detections = detector.detect(img)
        if not detections:
            continue

        # pick the highest-score detection
        det = max(detections, key=lambda d: d["score"])
        kps = det["kps"]

        if len(kps) != 5:
            continue

        aligned = align_face(img, kps)
        if aligned is None:
            continue

        emb = model.get_embedding(aligned)
        if emb is None:
            continue

        embeddings.append(emb.flatten())

    if not embeddings:
        return None

    # average all embeddings → consistent 512-D vector
    final_emb = np.mean(np.array(embeddings), axis=0)
    norm = np.linalg.norm(final_emb)
    if norm == 0:
        return None
    return final_emb / norm


# ---------------------------------------------
# APPROVE PENDING ENROLLMENT
# ---------------------------------------------
def process_pending_approve(pending_id):
    conn = db_conn()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, name, temp_folder FROM pending_enrollments WHERE id=?",
        (pending_id,)
    )
    row = cur.fetchone()

    if not row:
        conn.close()
        return False, "pending not found"

    name = row["name"]
    temp_folder = Path(row["temp_folder"])

    if not temp_folder.exists():
        # cleanup DB row
        cur.execute("DELETE FROM pending_enrollments WHERE id=?", (pending_id,))
        conn.commit()
        conn.close()
        return False, "pending folder missing"

    # safe destination
    safe_name = sanitize_name(name)
    dest = ensure_dir(DATASET_DIR / safe_name)

    # move images from pending → dataset
    moved = False
    for src in sorted(temp_folder.glob("*.jpg")):
        try:
            shutil.move(str(src), str(dest / src.name))
            moved = True
        except:
            try:
                shutil.copy(str(src), str(dest / src.name))
                moved = True
            except:
                pass

    if not moved:
        conn.close()
        return False, "no images moved"

    # compute final user embedding
    emb = compute_folder_embedding(str(dest))
    if emb is None:
        conn.close()
        return False, "could not compute embeddings"

    # insert user
    cur.execute(
        "INSERT INTO users (name, folder) VALUES (?, ?)",
        (name, str(dest))
    )
    user_id = cur.lastrowid

    # store embedding as JSON
    # emb_list = emb.astype(float).tolist()
    
    emb_bytes = emb.astype("float32").tobytes()
    created_at = int(time.time())  # current UNIX timestamp

    cur.execute(
    "INSERT INTO user_embeddings (user_id, embedding, created_at) VALUES (?, ?, ?)",
    (user_id, emb_bytes, created_at)
)

    # cleanup pending
    cur.execute("DELETE FROM pending_enrollments WHERE id=?", (pending_id,))
    conn.commit()
    conn.close()

    try:
        remove_dir(temp_folder)
    except:
        pass

    return True, {"user_id": user_id, "name": name}
