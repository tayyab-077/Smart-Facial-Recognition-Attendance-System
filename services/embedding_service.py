# services/embedding_service.py
# ------------------------------------------------------
# Compare face embedding with DB embeddings
# ------------------------------------------------------

import numpy as np
from database.db import db_conn

def find_top_k_users(embedding, k=2):
    """
    Returns top-k matching users sorted by similarity (desc)

    Output:
    [
      {"user_id": 1, "name": "A", "score": 0.93},
      {"user_id": 2, "name": "B", "score": 0.82}
    ]
    """

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

    results = []

    for user_id, name, emb_blob in rows:
        if emb_blob is None:
            continue

        db_emb = np.frombuffer(emb_blob, dtype=np.float32).copy()
        db_emb /= (np.linalg.norm(db_emb) + 1e-6)

        score = float(np.dot(embedding, db_emb))

        results.append({
            "user_id": user_id,
            "name": name,
            "score": score
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:k]