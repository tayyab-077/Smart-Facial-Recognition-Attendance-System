# services/embedding_service.py
# ------------------------------------------------------
# Compare face embedding with DB embeddings
# ------------------------------------------------------

import numpy as np
from database.db import db_conn


def find_best_user(embedding, threshold=0.70, debug=False):
    """
    embedding : np.ndarray (512,) or (1,512)
    threshold : cosine similarity threshold
    debug     : print similarity scores
    """

    # Normalize input embedding
    embedding = embedding.reshape(-1).astype(np.float32)
    embedding /= (np.linalg.norm(embedding) + 1e-6)

    db = db_conn()
    cur = db.cursor()

    cur.execute("""
        SELECT u.id, u.name, e.embedding
        FROM users u
        JOIN user_embeddings e ON u.id = e.user_id
    """)

    rows = cur.fetchall()
    db.close()

    if not rows:
        return None, 0.0

    best_user = None
    best_score = -1.0

    for user_id, name, emb_blob in rows:
        if emb_blob is None:
            continue

        # Convert DB BLOB → numpy
        db_emb = np.frombuffer(emb_blob, dtype=np.float32).copy()
        db_emb /= (np.linalg.norm(db_emb) + 1e-6)

        # Cosine similarity
        score = float(np.dot(embedding, db_emb))

        if debug:
            print(f"[MATCH] {name} (id={user_id}) → score={score:.4f}")

        if score > best_score:
            best_score = score
            best_user = {
                "user_id": user_id,
                "name": name
            }

    if debug:
        print(f"[BEST] score={best_score:.4f}, threshold={threshold}")

    # ✅ Threshold check ONLY ONCE
    if best_score < threshold:
        return None, best_score

    return best_user, best_score
