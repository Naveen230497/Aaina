import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime

DB_PATH = Path(".aaina/aaina_enterprise.db")

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY, password_hash TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS cases
                 (case_id TEXT PRIMARY KEY, username TEXT, urgent_count INTEGER, created_at TEXT)''')
    conn.commit()
    conn.close()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(username, password):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users VALUES (?, ?, ?)", 
                  (username, hash_password(password), datetime.now().isoformat()))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def verify_user(username, password):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT password_hash FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    if row and row[0] == hash_password(password):
        return True
    return False

def log_case(case_id, username, urgent_count):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO cases VALUES (?, ?, ?, ?)",
              (case_id, username, urgent_count, datetime.now().isoformat()))
    conn.commit()
    conn.close()

# Initialize on import
init_db()
def get_admin_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*), SUM(urgent_count) FROM cases")
    cases_row = c.fetchone()
    total_cases = cases_row[0] or 0
    total_urgent = cases_row[1] or 0
    
    c.execute("SELECT username, COUNT(*) as c FROM cases GROUP BY username ORDER BY c DESC LIMIT 5")
    top_users = c.fetchall()
    
    conn.close()
    return {
        "total_users": total_users,
        "total_cases": total_cases,
        "total_urgent": total_urgent,
        "top_users": top_users
    }
