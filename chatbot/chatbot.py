import csv
import os
from datetime import datetime

from chatbot.intent_engine import IntentEngine

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "..", "data", "chat_logs.csv")

DATA_PATH = "data/chat_logs.csv"

engine = IntentEngine()
engine.load_model()


def log_query(query, intent, confidence):
    file_exists = os.path.exists(DATA_PATH)

    with open(DATA_PATH, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["query", "intent", "confidence", "date"])
        writer.writerow([query, intent, round(confidence, 2), datetime.now().date()])


def chatbot_response(user_query):
    intent, confidence = engine.predict_intent(user_query)
    log_query(user_query, intent, confidence)
    return f"Intent: {intent} | Confidence: {confidence:.2f}"
