# api/admin_api.py
from flask import Blueprint, request, jsonify
from functools import wraps
import sqlite3
from pathlib import Path
import shutil
import json
import os
import time


# ml helper for embeddings (must exist in ml/)
from ml.embeddings import compute_folder_embedding



# ✅ ADD THIS HELPER FUNCTION (top of file or utils)🔑 
# Rule on Windows
# Never delete a folder immediately after file I/O + ML inference

# ✔ Best fix: retry deletion safely
# Replace your Step 7 with this robust deletion helper.

def safe_rmtree(path, retries=5, delay=0.5):
    import time, shutil
    for i in range(retries):
        try:
            if path.exists():
                shutil.rmtree(path)
            return True
        except Exception:
            time.sleep(delay)
    return False


admin_bp = Blueprint("admin_bp", __name__)

# --- simple admin_required decorator (uses session in app) ---
def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        from flask import session
        if not session.get("is_admin"):
            if request.is_json:
                return jsonify({"error": "unauthorized"}), 401
            return jsonify({"error": "unauthorized"}), 401
        return view(*args, **kwargs)
    return wrapped

# DB path relative to project root (avoid circular imports)
BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "database" / "attendance.db"

print("USING DATABASE:", DB_PATH)
print("ABSOLUTE PATH:", os.path.abspath(DB_PATH))



# def db_conn_local():
#     conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
#     conn.row_factory = sqlite3.Row
#     return conn


# ------------------------------------
# Enable WAL mode (MOST IMPORTANT)
# ✅ WAL = Write-Ahead Logging
# ✅ Allows reads while writing
# WAL = Write-Ahead Logging

# Without WAL:
# SQLite locks the entire database during a write ❌

# With WAL:
# One writer + many readers can work together,
# Reads do NOT block writes, Writes do NOT block reads
# ------------------------------------------
def db_conn_local():
    conn = sqlite3.connect(str(DB_PATH), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    # 🔥 IMPORTANT
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")

    return conn

# -------------------------
# Pending list
# -------------------------
@admin_bp.route("/pending", methods=["GET"])
@admin_required
def list_pending():
    conn = db_conn_local()
    cur = conn.cursor()
    cur.execute("SELECT id, name, temp_folder, requested_at FROM pending_enrollments ORDER BY requested_at DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(rows)

# -------------------------
# Users list
# -------------------------
@admin_bp.route("/users", methods=["GET"])
@admin_required
def list_users():
    conn = db_conn_local()
    cur = conn.cursor()

    cur.execute(" SELECT id, name, folder, created_at, admin_note FROM users ORDER BY id DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(rows)



# -------------------------
# Approve pending (immediate)
# -------------------------
@admin_bp.route("/approve", methods=["POST"])
@admin_required
def approve_pending():
    import time
    from datetime import datetime

    data = request.get_json() or {}
    pid = data.get("pending_id")
    if pid is None:
        return jsonify({"error": "pending_id required"}), 400

    conn = db_conn_local()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, name, temp_folder FROM pending_enrollments WHERE id=?",
        (pid,)
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "pending not found"}), 404

    name = row["name"]
    temp_folder = Path(row["temp_folder"])

    if not temp_folder.exists():
        cur.execute("DELETE FROM pending_enrollments WHERE id=?", (pid,))
        conn.commit()
        conn.close()
        return jsonify({"error": "pending folder missing"}), 500

    # ------------------------------------------------
    # 1️⃣ Prepare dataset folder
    # ------------------------------------------------
    safe_name = "".join(c for c in name if c.isalnum() or c in "_- ").strip()
    safe_name = safe_name.replace(" ", "_")

    dataset_dir = Path(BASE_DIR) / "storage" / "dataset"
    dataset_dir.mkdir(parents=True, exist_ok=True)

    # temporary folder (needed for NOT NULL folder column)
    temp_dest = dataset_dir / f"{safe_name}__pending"
    temp_dest.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------
    # 2️⃣ Insert user with folder
    # ------------------------------------------------
    created_at = int(time.time())
    created_at_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(
        "INSERT INTO users (name, folder, created_at) VALUES (?, ?, ?)",
        (name, str(temp_dest), created_at_str)
    )
    user_id = cur.lastrowid

    # ------------------------------------------------
    # 3️⃣ Rename temp folder to final folder: name__uID
    # ------------------------------------------------
    final_dest = dataset_dir / f"{safe_name}__u{user_id}"
    temp_dest.rename(final_dest)

    # update folder path in DB
    cur.execute(
        "UPDATE users SET folder=? WHERE id=?",
        (str(final_dest), user_id)
    )

    # ------------------------------------------------
    # 4️⃣ Move images (rename to avoid overwrite)
    # ------------------------------------------------
    moved_any = False
    for i, src in enumerate(sorted(temp_folder.glob("*.*"))):
        try:
            new_name = f"u{user_id}_{int(time.time())}_{i}{src.suffix}"
            target = final_dest / new_name
            shutil.move(str(src), str(target))
            moved_any = True
        except Exception as e:
            print("Move failed:", e)

    if not moved_any:
        conn.rollback()
        conn.close()
        return jsonify({"error": "no images moved"}), 500

    # ------------------------------------------------
    # 5️⃣ Compute embedding
    # ------------------------------------------------
    emb = compute_folder_embedding(str(final_dest))
    if emb is None:
        conn.rollback()
        safe_rmtree(final_dest)  # clean partially moved images
        conn.close()
        return jsonify({
            "error": "face_quality_low",
            "message": "Face images are too blurry / dark / unclear. Please re-enroll with better lighting and camera stability.",
            "tips": [
                "Ensure face is well-lit",
                "Look straight at camera",
                "Do not move while capturing",
                "Keep face close to camera"
            ]
        }), 400

    # ------------------------------------------------
    # 6️⃣ Store embedding
    # ------------------------------------------------
    emb_bytes = emb.astype("float32").tobytes()
    cur.execute(
        "INSERT INTO user_embeddings (user_id, embedding, created_at) "
        "VALUES (?, ?, ?)",
        (user_id, emb_bytes, created_at)
    )

    # ------------------------------------------------
    # 7️⃣ Cleanup pending
    # ------------------------------------------------
    cur.execute("DELETE FROM pending_enrollments WHERE id=?", (pid,))
    conn.commit()
    conn.close()

    # ------------------------------------------------
    # 8️⃣ Remove pending folder completely (SAFE)
    # ------------------------------------------------
    deleted = safe_rmtree(temp_folder)
    if not deleted:
        print("WARNING: Pending folder could not be deleted:", temp_folder)
    else:
        print("Pending folder deleted:", temp_folder)

    # ------------------------------------------------
    # ✅ Return updated info for frontend
    # ------------------------------------------------
    return jsonify({
        "status": "approved",
        "pending_id": pid,
        "user_id": user_id,
        "folder": final_dest.name,
        "name": name  # frontend uses this
    })


#Reject users
@admin_bp.route("/reject", methods=["POST"])
@admin_required
def reject_pending():
    data = request.get_json() or {}
    pid = data.get("pending_id")

    if not pid:
        return jsonify({"error": "pending_id required"}), 400

    conn = db_conn_local()
    cur = conn.cursor()

    cur.execute(
        "SELECT temp_folder FROM pending_enrollments WHERE id=?",
        (pid,)
    )
    row = cur.fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "pending enrollment not found"}), 404

    temp_folder = Path(row["temp_folder"])

    print("REJECT → temp_folder:", temp_folder)
    print("EXISTS:", temp_folder.exists())

    # 🔥 Delete folder properly
    try:
        if temp_folder.exists():
            shutil.rmtree(temp_folder)
            print("Pending folder deleted successfully")
    except Exception as e:
        conn.close()
        print("ERROR deleting pending folder:", e)
        return jsonify({
            "error": "failed to delete pending folder",
            "details": str(e)
        }), 500

    # Remove DB row
    cur.execute("DELETE FROM pending_enrollments WHERE id=?", (pid,))
    conn.commit()
    conn.close()

    return jsonify({"status": "rejected", "pending_id": pid})


# -------------------------
# update_user
# -------------------------

@admin_bp.route("/update_user", methods=["POST"])
@admin_required
def update_user():
    data = request.get_json() or {}
    uid = data.get("id")
    name = data.get("name")

    if not uid or not name:
        return jsonify({"error": "id and name required"}), 400

    conn = db_conn_local()
    cur = conn.cursor()

    cur.execute("UPDATE users SET name=? WHERE id=?", (name, uid))
    conn.commit()
    conn.close()

    return jsonify({"status": "updated", "user_id": uid})


# -------------------------
# delete_user
# -------------------------

@admin_bp.route("/delete_user", methods=["POST"])
@admin_required
def delete_user():
    data = request.get_json() or {}
    uid = data.get("id")
    if not uid:
        return jsonify({"error": "id required"}), 400

    conn = db_conn_local()
    cur = conn.cursor()

    # get folder to delete
    cur.execute("SELECT folder FROM users WHERE id=?", (uid,))
    row = cur.fetchone()

    if row:
        folder = row["folder"]
        try:
            shutil.rmtree(folder, ignore_errors=True)
        except:
            pass

    # delete DB rows
    cur.execute("DELETE FROM attendance WHERE user_id=?", (uid,))
    cur.execute("DELETE FROM user_embeddings WHERE user_id=?", (uid,))
    cur.execute("DELETE FROM users WHERE id=?", (uid,))

    conn.commit()
    conn.close()

    return jsonify({"status": "deleted", "user_id": uid})


# ---------------------
# Filters attendance by date / user / device.
# ---------------------

@admin_bp.route("/attendance", methods=["POST"])
@admin_required
def admin_attendance():
    data = request.get_json() or {}
    date = data.get("date")
    user_id = data.get("user_id")
    device = data.get("device")

    conn = db_conn_local()
    cur = conn.cursor()

    q = """
        SELECT a.user_id, u.name, a.timestamp, a.device
        FROM attendance a 
        JOIN users u ON a.user_id = u.id 
        WHERE 1=1
    """
    params = []

    if date:
        q += " AND date(a.timestamp) = date(?)"
        params.append(date)

    if user_id:
        q += " AND a.user_id = ?"
        params.append(user_id)

    if device:
        q += " AND a.device = ?"
        params.append(device)

    q += " ORDER BY a.timestamp DESC"

    cur.execute(q, params)
    rows = [dict(r) for r in cur.fetchall()]

    conn.close()
    return jsonify(rows)
