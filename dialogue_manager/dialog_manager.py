from nlu_engine.intent_parser import detect_intent
from nlu_engine.entity_extractor import extract_entities


def handle_dialog(user_msg: str, slots: dict | None = None):
    """
    Main dialog handler
    """

    intent = detect_intent(user_msg)

    # Auto-extract slots if not provided
    if slots is None:
        slots = extract_entities(user_msg)

    # ---------- GREETING ----------
    if intent == "greet":
        return "Hello 👋 I’m your BankBot. How can I help you today?"

    # ---------- CHECK BALANCE ----------
    if intent == "check_balance":
        accounts = slots.get("account_number", [])

        if not accounts:
            return "⚠️ Please provide the account number."

        account = accounts[0]
        return f"💰 Your account {account} has a balance of ₹45,000."

    # ---------- TRANSFER MONEY ----------
    if intent == "transfer_money":
        accounts = slots.get("account_number", [])
        amounts = slots.get("amount", [])

        if not amounts:
            return "⚠️ Please provide the amount to transfer."

        if not accounts:
            return "⚠️ Please provide the destination account number."

        amount = amounts[0].replace("₹", "").replace(",", "")
        account = accounts[0]

        return f"✅ Successfully transferred ₹{amount} to account {account}."

    # ---------- FALLBACK ----------
    return "🤔 I didn’t understand that. Try asking about balance or money transfer."

