def detect_intent(msg: str) -> str:
    msg = msg.lower()

    # 🔒 Balance FIRST
    if "balance" in msg or "check balance" in msg:
        return "check_balance"

    if "transfer" in msg or "send money" in msg:
        return "transfer_money"

    if "hi" in msg or "hello" in msg:
        return "greet"

    return "fallback"

