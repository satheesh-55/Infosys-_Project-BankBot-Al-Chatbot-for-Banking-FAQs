from database.db import get_conn
from database.security import hash_password, verify_password
from datetime import datetime

def create_account(name, acc_no, acc_type, balance, password):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("INSERT OR IGNORE INTO users(name) VALUES (?)", (name,))
    pwd_hash = hash_password(password)

    cur.execute("""
    INSERT INTO accounts(account_number, user_name, account_type, balance, password_hash)
    VALUES (?, ?, ?, ?, ?)
    """, (acc_no, name, acc_type, balance, pwd_hash))

    conn.commit()
    conn.close()

def get_account(acc_no):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    SELECT account_number, user_name, account_type, balance, password_hash
    FROM accounts WHERE account_number=?
    """, (acc_no,))
    row = cur.fetchone()
    conn.close()
    return row

def list_accounts():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT account_number, user_name FROM accounts")
    rows = cur.fetchall()
    conn.close()
    return rows

def transfer_money(from_acc, to_acc, amount, password):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT balance, password_hash FROM accounts WHERE account_number=?", (from_acc,))
    row = cur.fetchone()
    if not row:
        return "❌ Invalid sender account"

    balance, pwd_hash = row
    if not verify_password(password, pwd_hash):
        return "❌ Incorrect password"

    if balance < amount:
        return "❌ Insufficient balance"

    # Transaction (ACID)
    cur.execute("UPDATE accounts SET balance = balance - ? WHERE account_number=?", (amount, from_acc))
    cur.execute("UPDATE accounts SET balance = balance + ? WHERE account_number=?", (amount, to_acc))

    cur.execute("""
    INSERT INTO transactions(from_account, to_account, amount, timestamp)
    VALUES (?, ?, ?, ?)
    """, (from_acc, to_acc, amount, datetime.now().isoformat()))

    conn.commit()
    conn.close()
    return "✅ Transfer Successful"
