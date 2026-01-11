from chatbot.intent_engine import IntentEngine
from chatbot.chatbot import chatbot_response

engine = IntentEngine()
engine.load_model()

while True:
    q = input("User: ")
    if q.lower() == "exit":
        break
    print(chatbot_response(q))
