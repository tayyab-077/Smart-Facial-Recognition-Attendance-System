# user_api.py

from flask import Blueprint, request, jsonify
from utils.encoding import b64_to_cv2
from ml.embeddings import get_embedding_model
from services.embedding_service import find_top_k_users
from services.attendance_service import mark_attendance

# -----------------------------
# Load SCRFD + alignment ONCE
# -----------------------------
from ml.scrfd_detector import SCRFDDetector
from ml.face_align import align_face

scrfd = SCRFDDetector()          # loads ONNX model once
embedding_model = get_embedding_model()     # loads face embedding model once


# =========================
# Face Recognition Constants
# =========================
REJECT_THRESHOLD = 0.70
STRONG_ACCEPT_THRESHOLD = 0.92
TOP2_MARGIN = 0.10

# FRAME_VOTES_REQUIRED = 3


# ---------------------------------------
user_bp = Blueprint("user_bp", __name__)
# ---------------------------------------

@user_bp.route("/recognize", methods=["POST"])
def recognize():
    payload = request.get_json() or {}
    img_b64 = payload.get("image")

    if not img_b64:
        return jsonify({"recognized": False, "error": "image required"}), 400

    img = b64_to_cv2(img_b64)
    if img is None:
        return jsonify({"recognized": False, "error": "invalid image"}), 400

    # ------------------------------------------------
    # STEP 1: FACE DETECTION (STRICT)
    # ------------------------------------------------
    faces = scrfd.detect(img, conf_threshold=0.3)

    if len(faces) == 0:
        return jsonify({
            "recognized": False,
            "reason": "No face detected",
            "score": 0
        }), 200

    if len(faces) > 1:
        return jsonify({
            "recognized": False,
            "reason": "Multiple faces detected",
            "score": 0
        }), 200

    # face = max(faces, key=lambda f: f["score"])

    face = faces[0]
    kps = face["kps"]

    # ------------------------------------------------
    # STEP 2: ALIGN + EMBEDDING
    # ------------------------------------------------
    try:
        aligned_face = align_face(img, kps)
    except Exception as e:
        return jsonify({
            "recognized": False,
            "error": "Face alignment failed",
            "details": str(e),
            "score": 0
        }), 500

    emb = embedding_model.get_embedding(aligned_face)
    if emb is None:
        return jsonify({
            "recognized": False,
            "error": "Embedding failed",
            "score": 0
        }), 400


    top_matches = find_top_k_users(emb, k=2)

    if not top_matches:
        return jsonify({
            "recognized": False,
            "reason": "No enrolled users",
            "score": 0
        }), 200

    best = top_matches[0]
    second = top_matches[1] if len(top_matches) > 1 else None

    score = best["score"]

    # ------------------------------------------------
    # STEP 4: HARD REJECT
    # ------------------------------------------------
    if score < REJECT_THRESHOLD:
        return jsonify({
            "recognized": False,
            "reason": "Unknown user",
            "score": score
        }), 200

    # ------------------------------------------------
    # STEP 5: AMBIGUITY CHECK (CRITICAL)
    # ------------------------------------------------
    if second:
        margin = score - second["score"]
        if margin < TOP2_MARGIN:
            return jsonify({
                "recognized": False,
                "reason": "Face too similar to another user",
                "score": score,
                "borderline": True
            }), 200

    # ------------------------------------------------
    # STEP 6: ATTENDANCE
    # ------------------------------------------------
    borderline = score < STRONG_ACCEPT_THRESHOLD
    device = payload.get("device", "camera")

    attendance_result = mark_attendance(best["user_id"], device)

    return jsonify({
        "recognized": True,
        "user_id": best["user_id"],
        "name": best["name"],
        "score": score,
        "borderline": borderline,
        "attendance": attendance_result
    })

# -----------------------------------
# Save Admin Note
# -----------------------------------
@user_bp.route("/save_note", methods=["POST"])
def save_note():
    data = request.get_json()
    user_id = data.get("id")
    note = data.get("note", "")

    from database.db import db_conn
    db = db_conn()
    cur = db.cursor()

    cur.execute("UPDATE users SET admin_note = ? WHERE id = ?", (note, user_id))
    db.commit()
    db.close()

    return jsonify({"status": "ok", "message": "note saved"})
