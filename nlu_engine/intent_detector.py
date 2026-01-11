def detect_intent(text: str) -> str:
    text = text.lower()

    if any(word in text for word in ["balance", "balnce", "bal"]):
        return "check_balance"

    if any(word in text for word in ["news", "latest", "current"]):
        return "latest_news"

    if any(word in text for word in ["transfer", "send money"]):
        return "transfer_money"

    return "general"




