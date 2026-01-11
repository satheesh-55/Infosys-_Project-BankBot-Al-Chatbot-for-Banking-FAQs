from backend.database import SessionLocal, ChatLog
from backend.nlu.intent_classifier import IntentClassifier


classifier = IntentClassifier()


def handle_chat(user_text: str):
    intent, confidence = classifier.predict(user_text)

    success = 1 if confidence >= 0.70 else 0

    db = SessionLocal()
    log = ChatLog(
        user_query=user_text,
        predicted_intent=intent,
        confidence=confidence,
        success=success
    )
    db.add(log)
    db.commit()
    db.close()

    response = generate_response(intent)

    return {
        "response": response,
        "intent": intent,
        "confidence": round(confidence, 2),
        "success": success
    }


def generate_response(intent: str):
    responses = {
        "check_balance": "Your account balance is ₹25,000.",
        "transfer_money": "Money transfer initiated successfully.",
        "card_block": "Your card has been blocked for security.",
        "llm_fallback": "I am not sure about that. Let me connect you to support."
    }

    return responses.get(intent, "Sorry, I didn’t understand that.")
