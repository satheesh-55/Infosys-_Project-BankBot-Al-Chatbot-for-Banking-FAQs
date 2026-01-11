# ==============================
# Dialogue Manager
# ==============================

from nlu_engine.intent_detector import detect_intent
from database.bank_service import check_balance, transfer_money
from llm.llm_groq import grok_answer


def handle_dialogue(user_input: str) -> str:
    if not user_input or not user_input.strip():
        return "⚠️ Please enter a message."

    intent = detect_intent(user_input)

    # -------- GREETING --------
    if intent == "greet":
        return "👋 Hello! I’m BankBot. How can I help you?"

    # -------- CHECK BALANCE --------
    if intent == "check_balance":
        account = "999001"
        balance = check_balance(account)
        return f"💰 Your account {account} has a balance of ₹{balance}."

    # -------- TRANSFER MONEY --------
    if intent == "transfer_money":
        return transfer_money(
            from_account="999001",
            to_account="999002",
            amount=1000
        )

    # -------- FALLBACK TO LLM --------
    return grok_answer(user_input)










