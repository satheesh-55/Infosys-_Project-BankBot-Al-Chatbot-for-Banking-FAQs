import sqlite3
import os

DB_PATH = "database/bank.db"

os.makedirs("database", exist_ok=True)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# USERS TABLE (LOGIN SYSTEM)
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# ACCOUNTS TABLE
cur.execute("""
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    account_number TEXT UNIQUE,
    account_type TEXT,
    balance REAL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
""")

# TRANSACTIONS TABLE
cur.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_number TEXT,
    type TEXT,
    amount REAL,
    target TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()
conn.close()

print("✅ Database initialized")
