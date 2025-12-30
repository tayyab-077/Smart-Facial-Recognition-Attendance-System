-- ==========================================
--  DATABASE SCHEMA FOR EMBEDDING-BASED SYSTEM
--  Facial Attendance System (Final)
-- ==========================================

PRAGMA foreign_keys = ON;

-- -----------------------------
-- ADMINS
-- -----------------------------
CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------
-- USERS (Students/Employees)
-- -----------------------------

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    folder TEXT NOT NULL,
    admin_note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)

-- -----------------------------
-- USER EMBEDDINGS (128-d vector)
-- -----------------------------
CREATE TABLE IF NOT EXISTS user_embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    embedding BLOB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- -----------------------------
-- PENDING ENROLLMENTS
-- -----------------------------
CREATE TABLE IF NOT EXISTS pending_enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    temp_folder TEXT NOT NULL,
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------
-- ATTENDANCE LOGS
-- -----------------------------
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    device TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
