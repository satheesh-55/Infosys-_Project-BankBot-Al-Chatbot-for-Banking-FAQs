import streamlit as st
import json, os, re
import pandas as pd
from datetime import datetime

# =================================================
# CONFIG
# =================================================
st.set_page_config(
    page_title="Satheesh's BankBot",
    page_icon="🏦",
    layout="wide"
)

INTENT_FILE = "intents.json"
HISTORY_FILE = "query_history.json"
TX_FILE = "transaction_history.json"
REQUEST_FILE = "requests.json"

# =================================================
# THEME
# =================================================
dark_mode = st.toggle("🌙 Dark Mode")

# =================================================
# CSS
# =================================================
st.markdown(f"""
<style>
.stApp {{
    background-color: {"#0e1117" if dark_mode else "#f5f7fb"};
    color: {"#e5e7eb" if dark_mode else "#0b2545"};
}}
h1 {{ font-weight: 800; color: {"#60a5fa" if dark_mode else "#0b3c5d"}; }}
h2, h3 {{ font-weight: 700; color: {"#93c5fd" if dark_mode else "#1f4e79"}; }}
button {{
    background-color: #1f9d55 !important;
    color: white !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
}}
button:hover {{ background-color: #168f4a !important; }}
div[data-testid="metric-container"] {{
    background-color: {"#161b22" if dark_mode else "white"};
    border-radius: 14px;
    padding: 14px;
    box-shadow: 0 6px 18px rgba(0,0,0,0.15);
}}
table {{
    background-color: {"#161b22" if dark_mode else "white"};
}}
</style>
""", unsafe_allow_html=True)

# =================================================
# LOAD + AUTO-MIGRATE INTENTS
# =================================================
with open(INTENT_FILE, "r") as f:
    raw_intents = json.load(f)

intents = {}
for intent, data in raw_intents.items():
    if isinstance(data, list):
        intents[intent] = {
            "description": intent.replace("_", " ").title(),
            "examples": data
        }
    else:
        intents[intent] = data

# =================================================
# SESSION STATE (PERSISTENT)
# =================================================
if "history" not in st.session_state:
    st.session_state.history = json.load(open(HISTORY_FILE)) if os.path.exists(HISTORY_FILE) else []

if "tx_history" not in st.session_state:
    st.session_state.tx_history = json.load(open(TX_FILE)) if os.path.exists(TX_FILE) else []

if "requests" not in st.session_state:
    st.session_state.requests = json.load(open(REQUEST_FILE)) if os.path.exists(REQUEST_FILE) else []

# =================================================
# UTIL
# =================================================
def get_entity(entities, etype):
    for e in entities:
        if e["Type"] == etype:
            return e["Entity"]
    return None

# =================================================
# INTENT PREDICTION
# =================================================
def predict_intents(text, top_n=5):
    text = text.lower()
    scores = []
    for intent, data in intents.items():
        score = sum(1 for ex in data["examples"] if ex.lower() in text)
        scores.append((intent, score))
    scores.sort(key=lambda x: x[1], reverse=True)
    total = sum(s for _, s in scores) or 1
    return [{"intent": i, "confidence": round(s/total, 3)} for i,s in scores[:top_n]]

# =================================================
# ENTITY EXTRACTION
# =================================================
def extract_entities(text):
    entities = []
    working = text

    for ifsc in re.findall(r"\b[A-Z]{4}0[A-Z0-9]{6}\b", working):
        entities.append({"Entity": ifsc, "Type": "IFSC_CODE"})
        working = working.replace(ifsc, " ")

    for acc in re.findall(r"\b\d{10,16}\b", working):
        entities.append({"Entity": acc, "Type": "ACCOUNT_NUMBER"})
        working = working.replace(acc, " ")

    for d in re.findall(r"\b\d{2}[/-]\d{2}[/-]\d{4}\b", working):
        entities.append({"Entity": d, "Type": "DATE"})
        working = working.replace(d, " ")

    currency_map = {"₹": "INR", "$": "USD", "€": "EUR"}
    for sym, code in currency_map.items():
        for amt in re.findall(fr"\{sym}\d+(?:,\d{{3}})*", working):
            entities.append({"Entity": amt.replace(sym,"").replace(",",""), "Type": "AMOUNT"})
            entities.append({"Entity": code, "Type": "CURRENCY"})
            working = working.replace(amt, " ")

    for amt in re.findall(r"\b\d{1,6}\b", working):
        entities.append({"Entity": amt, "Type": "AMOUNT"})

    if "savings" in text.lower():
        entities.append({"Entity": "Savings", "Type": "ACCOUNT_TYPE"})
    if "checking" in text.lower():
        entities.append({"Entity": "Checking", "Type": "ACCOUNT_TYPE"})

    return entities

# =================================================
# ACTION HANDLER
# =================================================
def execute_action(intent, entities):
    now = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    types = {e["Type"] for e in entities}

    approval_intents = ["open_new_account", "change_pin", "apply_loan", "update_kyc"]

    if intent == "transfer_money":
        if "AMOUNT" not in types or "ACCOUNT_NUMBER" not in types:
            return "⚠️ Amount or account number missing"

        tx = {
            "time": now,
            "account": get_entity(entities, "ACCOUNT_NUMBER"),
            "account_type": get_entity(entities, "ACCOUNT_TYPE") or "Unknown",
            "amount": int(get_entity(entities, "AMOUNT")),
            "currency": get_entity(entities, "CURRENCY") or "INR"
        }

        st.session_state.tx_history.append(tx)
        json.dump(st.session_state.tx_history, open(TX_FILE, "w"), indent=2)
        return "✅ Transfer recorded successfully"

    if intent in approval_intents:
        req = {
            "time": now,
            "intent": intent,
            "status": "PENDING",
            "details": entities
        }
        st.session_state.requests.append(req)
        json.dump(st.session_state.requests, open(REQUEST_FILE, "w"), indent=2)
        return "🕒 Request submitted for approval"

    if intent == "check_balance":
        return "💰 Balance: ₹48,920"

    return "ℹ️ Request processed"

# =================================================
# UI
# =================================================
st.title("🏦 Satheesh's BankBot")

tabs = st.tabs([
    "🧠 Analyzer",
    "🛠 Intent Manager",
    "📜 History",
    "📊 Analytics",
    "📥 Requests"
])

# ---------------- ANALYZER ----------------
with tabs[0]:
    query = st.text_area("Enter banking query")

    if st.button("Analyze"):
        preds = predict_intents(query)
        ents = extract_entities(query)

        c1, c2, c3 = st.columns(3)
        c1.metric("Intent", preds[0]["intent"])
        c2.metric("Confidence", f"{preds[0]['confidence']*100:.1f}%")
        c3.metric("Entities", len(ents))

        st.bar_chart(pd.DataFrame({"Confidence (%)": [preds[0]["confidence"] * 100]}))

        with st.expander("🧾 Extracted Entities"):
            st.table(pd.DataFrame(ents))

        result = execute_action(preds[0]["intent"], ents)
        st.success(result)

        st.session_state.history.append({
            "time": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
            "query": query,
            "intent": preds[0]["intent"],
            "confidence": preds[0]["confidence"]
        })
        json.dump(st.session_state.history, open(HISTORY_FILE, "w"), indent=2)

# ---------------- INTENT MANAGER ----------------
with tabs[1]:
    for intent, data in intents.items():
        with st.expander(intent):
            st.markdown(f"**Description:** {data['description']}")
            for ex in data["examples"]:
                st.write("•", ex)

# ---------------- HISTORY ----------------
with tabs[2]:
    col1, col2 = st.columns(2)

    if col1.button("🧹 Clear Query History"):
        st.session_state.history = []
        json.dump([], open(HISTORY_FILE, "w"))

    if col2.button("🧹 Clear Transaction History"):
        st.session_state.tx_history = []
        json.dump([], open(TX_FILE, "w"))

    st.dataframe(pd.DataFrame(st.session_state.history), use_container_width=True)

# ---------------- ANALYTICS ----------------
with tabs[3]:
    if st.session_state.tx_history:
        df = pd.DataFrame(st.session_state.tx_history)
        st.bar_chart(df.groupby("account")["amount"].sum())
        st.bar_chart(df.groupby("account_type")["amount"].sum())
    else:
        st.info("No transactions yet")

# ---------------- REQUESTS ----------------
with tabs[4]:
    st.subheader("📥 Approval Requests")
    if st.session_state.requests:
        st.dataframe(pd.DataFrame(st.session_state.requests), use_container_width=True)
    else:
        st.info("No pending requests")

# =================================================
# FOOTER
# =================================================
st.markdown(
    "<center><small>Developed by <b>Satheesh</b> • Enterprise Banking NLU System</small></center>",
    unsafe_allow_html=True
)

























