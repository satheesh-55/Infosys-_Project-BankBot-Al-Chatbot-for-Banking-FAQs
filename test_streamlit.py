import streamlit as st
from nlu_engine.dialogue_handler import handle_dialogue

# =================================================
# PAGE CONFIG (MUST BE FIRST)
# =================================================
st.set_page_config(
    page_title="Satheesh's BankBot",
    page_icon="🏦",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# =================================================
# GLOBAL CSS (AURORA + GLASS UI)
# =================================================
st.markdown("""
<style>
:root {
  --primary: #38bdf8;
  --secondary: #6366f1;
  --accent: #22c55e;
  --bg-dark: #020617;
  --glass: rgba(255,255,255,0.10);
  --border-glass: rgba(255,255,255,0.25);
  --text-main: #f8fafc;
  --text-muted: #94a3b8;
}

/* ---------- APP BACKGROUND ---------- */
.stApp {
  font-family: Inter, -apple-system, BlinkMacSystemFont, sans-serif;
  color: var(--text-main);
  background:
    radial-gradient(40% 30% at 15% 20%, rgba(56,189,248,0.35), transparent 60%),
    radial-gradient(35% 30% at 85% 25%, rgba(99,102,241,0.35), transparent 60%),
    radial-gradient(30% 30% at 50% 80%, rgba(34,197,94,0.30), transparent 60%),
    linear-gradient(135deg, #020617, #020617);
  background-attachment: fixed;
}

/* ---------- TITLE ---------- */
h1 {
  text-align: center;
  font-weight: 800;
  color: var(--primary);
  text-shadow: 0 0 24px rgba(56,189,248,0.45);
}

/* ---------- CARDS ---------- */
.card {
  background: var(--glass);
  backdrop-filter: blur(18px);
  border: 1px solid var(--border-glass);
  border-radius: 20px;
  padding: 22px;
  box-shadow: 0 20px 40px rgba(0,0,0,0.45);
}

/* ---------- CHAT BUBBLES ---------- */
[data-testid="chat-message-user"] {
  background: linear-gradient(135deg, #2563eb, #1e40af);
  color: white;
  border-radius: 18px;
  padding: 14px 16px;
  box-shadow: 0 10px 30px rgba(37,99,235,0.35);
}

[data-testid="chat-message-assistant"] {
  background: var(--glass);
  backdrop-filter: blur(16px);
  border: 1px solid var(--border-glass);
  color: #e5e7eb;
  border-radius: 18px;
  padding: 14px 16px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.35);
}

/* ---------- CHAT INPUT ---------- */
[data-testid="stChatInput"] textarea {
  background: rgba(255,255,255,0.08);
  border-radius: 16px;
  border: 1px solid rgba(255,255,255,0.25);
  color: white;
  padding: 14px;
  font-size: 1rem;
}

[data-testid="stChatInput"] textarea:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 25px rgba(56,189,248,0.45);
}

/* ---------- BUTTONS ---------- */
.stButton > button {
  background: linear-gradient(135deg, #38bdf8, #6366f1);
  color: white;
  border-radius: 14px;
  padding: 10px 18px;
  font-weight: 600;
  border: none;
  box-shadow: 0 10px 25px rgba(56,189,248,0.45);
}

/* ---------- CLEAN ---------- */
footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# =================================================
# SESSION STATE
# =================================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# =================================================
# LOGIN PAGE
# =================================================
def login_page():
    st.title("🏦 BankBot Secure Login")

    with st.container():
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            if username and password:

                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Invalid credentials")

        st.markdown("</div>", unsafe_allow_html=True)

# =================================================
# CHATBOT PAGE
# =================================================
def chatbot_page():
    st.title("🏦 Satheesh's BankBot")
    st.markdown(
        "<div style='text-align:center;color:#94a3b8;'>Secure Banking • AI Assistant • Real-time Intelligence</div>",
        unsafe_allow_html=True
    )

    # Greeting
    if not st.session_state.chat_history:
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": "👋 Hello! I’m your **BankBot AI**. Ask me about balance, transactions, or latest banking updates."
        })

    # Render history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input
    user_input = st.chat_input("Ask about balance, transfer, loans, or news...")

    if user_input:
        st.session_state.chat_history.append(
            {"role": "user", "content": user_input}
        )

        with st.chat_message("assistant"):
            with st.spinner("🔐 Processing securely..."):
                response = handle_dialogue(user_input)
                st.markdown(response)

        st.session_state.chat_history.append(
            {"role": "assistant", "content": response}
        )

    if st.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.chat_history = []
        st.rerun()

# =================================================
# ROUTER
# =================================================
if not st.session_state.authenticated:
    login_page()
else:
    chatbot_page()







