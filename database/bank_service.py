# Mock database (replace with real DB later)
ACCOUNTS = {
    "886877": 45000,
    "999001": 120000,
    "12345667890": 8800
}

def get_balance(account_number: str):
    return ACCOUNTS.get(account_number)



