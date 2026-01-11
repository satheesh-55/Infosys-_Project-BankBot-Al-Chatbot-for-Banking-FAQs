import re

def parse_message(text):
    text = text.lower()
    entities = {}

    if "hi" in text or "hello" in text:
        intent = "greet"
    elif "transfer" in text:
        intent = "money_transfer"
    else:
        intent = "money_transfer"

    acc = re.search(r"\b\d{9,18}\b", text)
    if acc:
        entities["account"] = acc.group()

    amt = re.search(r"\b\d{3,}\b", text)
    if amt:
        entities["amount"] = amt.group()

    return intent, entities



import re

def parse_message(text):
    text = text.lower()

    if "balance" in text:
        return {"intent": "check_balance"}

    if "deposit" in text:
        amt = re.findall(r"\d+", text)
        return {"intent": "deposit", "amount": int(amt[0]) if amt else None}

    if "withdraw" in text:
        amt = re.findall(r"\d+", text)
        return {"intent": "withdraw", "amount": int(amt[0]) if amt else None}

    return {"intent": "fallback"}
