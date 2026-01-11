from database.bank_service import get_balance
from llm.llm_groq import grok_answer
from llm.web_search import web_search, latest_news
from nlu_engine.entity_extractor import extract_account_number

# Context memory
context = {
    "awaiting_account": False
}


def handle_dialogue(user_input: str) -> str:
    user_input = user_input.strip()
    lower_text = user_input.lower()

    # --------------------------------------------------
    # If bot is waiting for account number
    # --------------------------------------------------
    if context["awaiting_account"]:
        account = extract_account_number(user_input)

        if account:
            context["awaiting_account"] = False
            balance = get_balance(account)

            if balance is None:
                return f"I couldn’t find account {account} in our system."

            return f"The balance for account {account} is ₹{balance:,}."

        # Let LLM respond naturally
        return grok_answer(user_input)

    # --------------------------------------------------
    # Direct balance request with account
    # --------------------------------------------------
    account = extract_account_number(user_input)

    if account and "balance" in lower_text:
        balance = get_balance(account)

        if balance is None:
            return f"I couldn’t find account {account} in our system."

        return f"The balance for account {account} is ₹{balance:,}."

    # --------------------------------------------------
    # Balance request without account
    # --------------------------------------------------
    if "balance" in lower_text:
        context["awaiting_account"] = True
        return grok_answer(
            "User wants to check bank balance but did not provide account number. Ask politely for the account number."
        )

    # --------------------------------------------------
    # Latest news (REAL-TIME)
    # --------------------------------------------------
    if "latest news" in lower_text or "today news" in lower_text:
        return "📰 Latest News:\n" + latest_news()

    # --------------------------------------------------
    # Web search queries
    # --------------------------------------------------
    if any(word in lower_text for word in ["search", "google", "find", "who is", "what is", "latest"]):
        web_result = web_search(user_input)
        return web_result

    # --------------------------------------------------
    # Fallback → LLM
    # --------------------------------------------------
    return grok_answer(user_input)







