from chatbot.intents import detect_intent, extract_amount
from database.db import get_conn

def chatbot_response(text, acc_no):
    intent = detect_intent(text)
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT balance FROM users WHERE account_number=?", (acc_no,))
    balance = cur.fetchone()[0]

    if intent == "balance":
        return f"💰 Your current balance is ₹{balance}"

    if intent == "deposit":
        amt = extract_amount(text)
        if not amt:
            return "❌ Please mention amount to deposit"
        cur.execute("UPDATE users SET balance=balance+? WHERE account_number=?", (amt, acc_no))
        conn.commit()
        return f"✅ Deposited ₹{amt}"

    if intent == "withdraw":
        amt = extract_amount(text)
        if not amt:
            return "❌ Please mention amount"
        if amt > balance:
            return "❌ Insufficient balance"
        cur.execute("UPDATE users SET balance=balance-? WHERE account_number=?", (amt, acc_no))
        conn.commit()
        return f"✅ Withdrawn ₹{amt}"

    return "🤖 I can help with balance, deposit, withdraw"
