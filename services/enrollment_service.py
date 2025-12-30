# services/enrollment_service.py
# Helpers used by enroll endpoint (saves images, inserts pending DB record).


from pathlib import Path
import uuid
import base64
from database.db import db_conn
from utils.file_utils import ensure_dir
import time

BASE_DIR = Path(__file__).resolve().parents[1]
PENDING_DIR = BASE_DIR / "storage" / "pending"

def save_pending_images(name: str, images: list):
    pid = uuid.uuid4().hex
    dest = ensure_dir(PENDING_DIR / pid)
    saved = 0
    
    # for i, img_b64 in enumerate(images):
    #     header, body = (img_b64.split(",", 1) + [""])[:2]
    #     try:
    #         img_bytes = base64.b64decode(body or header)
    #         (dest / f"{i:03d}.jpg").write_bytes(img_bytes)
    #         saved += 1
    #     except Exception:
    #         pass
        
    #     import time

    for i, img_b64 in enumerate(images):
        header, body = (img_b64.split(",", 1) + [""])[:2]
        try:
            img_bytes = base64.b64decode(body or header)

            # unique filename in pending folder
            filename = f"p_{int(time.time())}_{i}.jpg"
            (dest / filename).write_bytes(img_bytes)

            saved += 1
        except Exception as e:
            print("Image save failed:", e)

    if saved == 0:
        return None, "no valid images"

    conn = db_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO pending_enrollments (name, temp_folder) VALUES (?, ?)", (name, str(dest)))
    conn.commit()
    pid_db = cur.lastrowid
    conn.close()
    return pid_db, str(dest)
