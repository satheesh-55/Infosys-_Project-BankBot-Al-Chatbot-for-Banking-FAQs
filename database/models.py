from database.db import get_connection

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        account_number TEXT UNIQUE,
        account_type TEXT,
        balance INTEGER,
        password TEXT
    )
    """)

    conn.commit()
    conn.close()
    print("✅ accounts table created")

if __name__ == "__main__":
    init_db()
