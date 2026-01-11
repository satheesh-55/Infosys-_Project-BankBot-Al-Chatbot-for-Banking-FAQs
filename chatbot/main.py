from cmath import log
import csv
import os
from datetime import datetime
from chatbot.nlu_engine import predict_intent

CHATLOG_PATH = "data/chat_logs.csv"

def chatbot_response(user_input):
    intent, confidence, entities = predict_intent(user_input)

    log = {
        "query": user_input,
        "intent": intent,
        "confidence": confidence,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "entities": str(entities)
    }

    df = pd.read_csv("data/chat_logs.csv")
    df.loc[len(df)] = log
    df.to_csv("data/chat_logs.csv", index=False)

    file_exists = os.path.exists(CHATLOG_PATH)

    with open(CHATLOG_PATH, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(
                ["query", "intent", "confidence", "entities", "date"]
            )
            str(entities),
            datetime.now().strftime("%Y-%m-%d")
        ])

    return {
        "intent": intent,
        "confidence": confidence,
        "entities": entities
    }
