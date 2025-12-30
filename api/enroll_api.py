# api/enroll_api.py
# Public enrollment endpoint that leverages services/enrollment_service.py.

from flask import Blueprint, request, jsonify
from services.enrollment_service import save_pending_images

enroll_bp = Blueprint("enroll_bp", __name__)

@enroll_bp.route("", methods=["POST"])
@enroll_bp.route("/", methods=["POST"])   # ← IMPORTANT FIX
def enroll():
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    images = data.get("images", [])
    if not name or not images:
        return jsonify({"error": "name and images required"}), 400

    pid_db, dest = save_pending_images(name, images)
    if not pid_db:
        return jsonify({"error": "no images saved"}), 400

    return jsonify({"status": "pending", "pending_id": pid_db})
