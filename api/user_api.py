# user_api.py

from flask import Blueprint, request, jsonify
from utils.encoding import b64_to_cv2
from ml.embeddings import get_embedding_model
from services.embedding_service import find_best_user
from services.attendance_service import mark_attendance

# -----------------------------
# Load SCRFD + alignment ONCE
# -----------------------------
from ml.scrfd_detector import SCRFDDetector
from ml.face_align import align_face

scrfd = SCRFDDetector()          # loads ONNX model once
embedding_model = get_embedding_model()     # loads face embedding model once

# ---------------------------------------
user_bp = Blueprint("user_bp", __name__)
# ---------------------------------------

@user_bp.route("/recognize", methods=["POST"])
def recognize():
    payload = request.get_json() or {}
    img_b64 = payload.get("image")

    if not img_b64:
        return jsonify({"error": "image required"}), 400

    # Decode base64 → OpenCV image
    img = b64_to_cv2(img_b64)
    if img is None:
        return jsonify({"error": "invalid image"}), 400

    # ------------------------------------------------------------
    # STEP 1: FACE DETECTION
    # ------------------------------------------------------------
    faces = scrfd.detect(img, conf_threshold=0.3)
    if not faces:
        return jsonify({"recognized": False, "reason": "No face detected", "score": 0}), 200

    # Pick the best face (highest confidence)
    face = max(faces, key=lambda r: r["score"])
    kps = face["kps"]  # 5 facial landmarks

    # ------------------------------------------------------------
    # STEP 2: ALIGN FACE
    # ------------------------------------------------------------
    try:
        aligned_face = align_face(img, kps)
    except Exception as e:
        return jsonify({
            "recognized": False,
            "error": "Face alignment failed",
            "details": str(e),
            "score": 0
        }), 500

    # ------------------------------------------------------------
    # STEP 3: EMBEDDING
    # ------------------------------------------------------------
    emb = embedding_model.get_embedding(aligned_face)
    if emb is None:
        return jsonify({
            "recognized": False,
            "error": "Embedding failed",
            "score": 0
        }), 400

    # ------------------------------------------------------------
    # STEP 4: MATCH USER
    # ------------------------------------------------------------
    threshold = payload.get("threshold", 0.70)
    borderline_threshold = 0.92  # similarity below this is borderline
    best, score = find_best_user(emb, threshold)

    if not best:
        return jsonify({
            "recognized": False,
            "reason": "Unknown user",
            "score": score,
            "borderline": score >= threshold and score < borderline_threshold
        }), 200

    # ------------------------------------------------------------
    # STEP 5: MARK ATTENDANCE
    # ------------------------------------------------------------
    device = payload.get("device", "camera")
    attendance_result = mark_attendance(best["user_id"], device)

    # Determine if borderline
    is_borderline = score < borderline_threshold

    return jsonify({
        "recognized": True,
        "user_id": best["user_id"],
        "name": best["name"],
        "score": score,
        "borderline": is_borderline,
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
