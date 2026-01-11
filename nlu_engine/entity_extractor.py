import re

def extract_account_number(text: str):
    match = re.search(r"\b\d{6,18}\b", text)
    return match.group() if match else None


