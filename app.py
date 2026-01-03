# app.py — cleaned embedding-based version
import os
import json
import base64
from pathlib import Path
from datetime import datetime
from functools import wraps 
import uuid
import sqlite3

from ml.download_models import download_if_missing

print("🚀 Starting app, ensuring models exist...")
download_if_missing()
print("✅ Models ready")

from flask import (
    Flask, render_template, request, jsonify, session,
    redirect, url_for, send_from_directory
)

# --- Blueprint Import (admin routes)
from api.admin_api import admin_bp

# ----- Import the user_api blueprint  
from api.user_api import user_bp

# ----- Import the enroll_api blueprint 
from api.enroll_api import enroll_bp


# --- Optional CV2 import ---
try:
    import numpy as np
    import cv2
    HAVE_CV2 = True
except Exception:
    HAVE_CV2 = False

# --- Embedding model import (for recognition) ---
# ml.embeddings should provide compute_folder_embedding and model loader

# from ml.embedding_model import EmbeddingModel

from ml.embeddings import get_embedding_model


# ------------------------------------------------------
# Paths / Config
# ------------------------------------------------------
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "database" / "attendance.db"

STORAGE_DIR = BASE_DIR / "storage"
PENDING_DIR = STORAGE_DIR / "pending"
DATASET_DIR = STORAGE_DIR / "dataset"
MODELS_DIR = STORAGE_DIR / "models"

for p in [DB_PATH.parent, PENDING_DIR, DATASET_DIR, MODELS_DIR]:
    p.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change_this_secret_for_prod")


# Register blueprint
app.register_blueprint(admin_bp, url_prefix="/api/admin")

# Register blueprint
app.register_blueprint(user_bp, url_prefix="/api")

# Register blueprint
app.register_blueprint(enroll_bp, url_prefix="/api/enroll")

# ------------------------------------------------------
# DB helper
# ------------------------------------------------------
def db_conn():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# ------------------------------------------------------
# Create tables (includes user_embeddings for Option A)
# ------------------------------------------------------
def ensure_tables():
    conn = db_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password_hash TEXT,
        created_at INTEGER DEFAULT CURRENT_TIMESTAMP
    )""")


    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        folder TEXT NOT NULL,
        admin_note TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    


    cur.execute("""
    CREATE TABLE IF NOT EXISTS pending_enrollments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        temp_folder TEXT NOT NULL,
        requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        device TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")

    # user_embeddings table: store embedding JSON text per user (option A)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_embeddings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        embedding BLOB NOT NULL,
        created_at INTEGER DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")
      

    conn.commit()
    conn.close()

ensure_tables()



# --- Create default admin ---
from werkzeug.security import generate_password_hash, check_password_hash
def ensure_default_admin():
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as c FROM admins")
    c = cur.fetchone()["c"]
    if c == 0:
        cur.execute("INSERT INTO admins (username, password_hash) VALUES (?,?)",
                    ("admin", generate_password_hash("admin123")))
        conn.commit()
    conn.close()

ensure_default_admin()

# ------------------------------------------------------
# Admin login decorator (for blueprint use)
# ------------------------------------------------------
def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            if request.is_json:
                return jsonify({"error": "unauthorized"}), 401
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped

# ------------------------------------------------------
# UI Routes
# ------------------------------------------------------
@app.route("/")
def dashboard():
    return render_template("dashboard.html")

@app.route("/enroll")
def enroll_page():
    return render_template("enroll.html")

@app.route("/attendance")
def attendance_page():
    return render_template("attendance.html")


@app.route("/users")
def users_page():
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, created_at, admin_note
        FROM users
        ORDER BY id ASC
    """)
    
    users = cur.fetchall()
    conn.close()
    return render_template("users.html", users=users)

# ------------------------------------------------------
# Admin auth pages
# ------------------------------------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "GET":
        return render_template("admin_login.html")

    data = request.form
    username = data.get("username", "")
    password = data.get("password", "")

    conn = db_conn()
    cur = conn.cursor()
    cur.execute("SELECT password_hash FROM admins WHERE username=?", (username,))
    row = cur.fetchone()
    conn.close()

    if not row or not check_password_hash(row["password_hash"], password):
        return render_template("admin_login.html", error="Invalid credentials")

    session["is_admin"] = True
    session["admin_username"] = username
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    return render_template("admin_dashboard.html")




# # ------------------------------------------------------
# # API: Enroll – save pending (unchanged)
# # ------------------------------------------------------
# @app.route("/api/enroll", methods=["POST"])
# def api_enroll():
#     payload = request.get_json()
#     name = payload.get("name", "").strip()
#     images = payload.get("images", [])

#     if not name or not images:
#         return jsonify({"error": "name and images required"}), 400

#     pid = uuid.uuid4().hex
#     dest = PENDING_DIR / pid
#     dest.mkdir(parents=True, exist_ok=True)

#     for i, img in enumerate(images):
#         header, body = img.split(",", 1) if "," in img else ("", img)
#         try:
#             img_bytes = base64.b64decode(body)
#             (dest / f"{i:03d}.jpg").write_bytes(img_bytes)
#         except:
#             pass

#     conn = db_conn()
#     cur = conn.cursor()
#     cur.execute("INSERT INTO pending_enrollments (name, temp_folder) VALUES (?, ?)",
#                 (name, str(dest)))
#     conn.commit()
#     row_id = cur.lastrowid
#     conn.close()

#     return jsonify({
#         "status": "pending",
#         "pending_id": row_id
#     })




# ------------------------------------------------------
# API: Static file
# ------------------------------------------------------
@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(str(BASE_DIR / "static"), filename)


# ------------------------------------------------------
# Run App
# ------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
