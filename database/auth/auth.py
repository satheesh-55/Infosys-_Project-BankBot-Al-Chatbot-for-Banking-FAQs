import bcrypt
from database.db import get_connection


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_account(account_number, username, account_type, balance, password):
    conn = get_connection()
    cur = conn.cursor()

    hashed = hash_password(password)

    cur.execute("""
        INSERT INTO users
        (account_number, username, account_type, balance, password)
        VALUES (?, ?, ?, ?, ?)
    """, (account_number, username, account_type, balance, hashed))

    conn.commit()
    conn.close()
    return True


def login_user(account_number, password):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT username, balance, password
        FROM users
        WHERE account_number = ?
    """, (account_number,))

    row = cur.fetchone()
    conn.close()

    if row and check_password(password, row[2]):
        return {
            "account_number": account_number,
            "username": row[0],
            "balance": row[1]
        }

    return None


if __name__ == "__main__":
    print("✅ Auth module loaded")

