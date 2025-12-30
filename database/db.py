# database/db.py
import sqlite3
from pathlib import Path


# BASE_DIR = Path(__file__).resolve().parents[1]
# DB_PATH = BASE_DIR / "database" / "attendance.db"

# def db_conn():
#     conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
#     conn.row_factory = sqlite3.Row
#     return conn


BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "database" / "attendance.db"

def db_conn():
    conn = sqlite3.connect(str(DB_PATH), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")

    return conn


def ensure_tables():
    conn = db_conn()
    cur = conn.cursor()

    # admins, users, pending_enrollments, attendance, user_embeddings (Option A)
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

# Ensure tables when module is imported
ensure_tables()
