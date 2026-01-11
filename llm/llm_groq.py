



# ==============================
# Groq LLM Wrapper (FINAL)
# ==============================

import os
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

# Load .env file
load_dotenv()

# Read API key
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError("❌ GROQ_API_KEY not found in .env file")

# Initialize LLM (ONCE)
_llm = ChatGroq(
    model="llama-3.1-8b-instant",
    temperature=0.3,
    api_key=GROQ_API_KEY
)


def grok_answer(user_input: str) -> str:
    """
    Takes user input string
    Returns LLM response string
    """

    response = _llm.invoke(
        [HumanMessage(content=user_input)]
    )

    return response.content








