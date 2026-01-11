# intent_engine.py

def predict_intent(text: str) -> dict:
    """
    Simple intent prediction logic.
    Can be replaced with ML / NLP later.
    """

    if not text:
        return {"intent": "empty", "confidence": 0.0}

    text = text.lower()

    if any(word in text for word in ["balance", "account"]):
        intent = "check_balance"
        confidence = 0.85
    elif any(word in text for word in ["loan", "credit"]):
        intent = "loan_query"
        confidence = 0.80
    elif any(word in text for word in ["card", "debit", "credit card"]):
        intent = "card_issue"
        confidence = 0.75
    else:
        intent = "fallback"
        confidence = 0.40

    return {
        "intent": intent,
        "confidence": confidence
    }

