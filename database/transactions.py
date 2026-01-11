from database.bank_crud import get_account, update_balance

def deposit(username, amount):
    acc = get_account(username)
    if not acc:
        return "❌ Account not found"

    new_balance = acc[1] + amount
    update_balance(username, new_balance)
    return f"✅ Deposited ₹{amount}. New balance: ₹{new_balance}"

def withdraw(username, amount):
    acc = get_account(username)
    if not acc:
        return "❌ Account not found"

    if acc[1] < amount:
        return "❌ Insufficient balance"

    new_balance = acc[1] - amount
    update_balance(username, new_balance)
    return f"💸 Withdrawn ₹{amount}. Balance: ₹{new_balance}"

