from fastapi import FastAPI
from pydantic import BaseModel

from bankbot_ai.backend.database import SessionLocal, ChatLog
from bankbot_ai.backend.nlu.intent_classifier import IntentClassifier

app = FastAPI(title="BankBot Backend")

# Load ML model once
clf = IntentClassifier()


# ---------- Request / Response Schemas ----------
class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    intent: str
    confidence: float


# ---------- Startup ----------
@app.on_event("startup")
def on_startup():
    # Ensure DB tables exist
    from bankbot_ai.backend.database import create_db
    create_db()


# ---------- Health ----------
@app.get("/")
def root():
    return {"status": "BankBot backend running"}


# ---------- Chat API ----------
@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    intent, confidence = clf.predict(req.message)

    # Log to DB
    db = SessionLocal()
    log = ChatLog(
        user_query=req.message,
        predicted_intent=intent,
        confidence=confidence,
        success=1 if confidence >= 0.5 else 0
    )
    db.add(log)
    db.commit()
    db.close()

    return {
        "intent": intent,
        "confidence": round(confidence, 3)
    }

