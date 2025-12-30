# services/attendance_service.py
from datetime import datetime
from database.db import db_conn

def mark_attendance(user_id, device="camera"):
    db = db_conn()
    cur = db.cursor()

    # 1️⃣ Verify user exists
    cur.execute("SELECT id FROM users WHERE id=?", (user_id,))
    if not cur.fetchone():
        db.close()
        return {"success": False, "reason": "User not found"}

    # 2️⃣ Prevent duplicate attendance
    today = datetime.now().strftime("%Y-%m-%d")
    cur.execute("""
        SELECT id FROM attendance
        WHERE user_id=? AND DATE(timestamp)=?
    """, (user_id, today))

    if cur.fetchone():
        db.close()
        return {"success": False, "reason": "Attendance already marked today"}

    # 3️⃣ Insert attendance
    cur.execute("""
        INSERT INTO attendance (user_id, timestamp, device)
        VALUES (?, ?, ?)
    """, (user_id, datetime.now(), device))

    db.commit()
    db.close()

    return {"success": True, "reason": "Attendance marked"}
