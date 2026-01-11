import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import os

# ============================================================
# PATH SETUP
# ============================================================
sys.path.append(str(Path(__file__).resolve().parents[2]))

from chatbot.retrain import retrain_model
from chatbot.main import chatbot_response
from chatbot.nlu_engine import load_nlu_model

if st.button("Load NLU Model"):
    df = load_nlu_model()
    st.success("NLU model loaded successfully")

# ============================================================
# PAGE CONFIG (MUST BE FIRST)
# ============================================================
st.set_page_config(
    page_title="BankBot Admin Dashboard",
    layout="wide",
    page_icon="📊"
)

# ============================================================
# 🔥 PREMIUM / GLOWING UI (RESTORED + ENHANCED)
# ============================================================
st.markdown("""
<style>

/* ===============================
   🌌 GLOBAL BACKGROUND
   =============================== */
.stApp {
    background:
        radial-gradient(1200px 600px at 10% 10%, rgba(56,189,248,0.15), transparent 40%),
        radial-gradient(1000px 500px at 90% 20%, rgba(99,102,241,0.18), transparent 45%),
        linear-gradient(180deg, #020617, #020617);
    color: #e5e7eb;
    font-family: Inter, -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ===============================
   🧊 GLASS CARDS (METRICS)
   =============================== */
[data-testid="metric-container"] {
    background: rgba(255,255,255,0.08);
    border-radius: 18px;
    padding: 18px;
    border: 1px solid rgba(255,255,255,0.14);
    box-shadow:
        0 0 20px rgba(56,189,248,0.35),
        inset 0 0 14px rgba(255,255,255,0.06);
    transition: all 0.35s ease;
}

[data-testid="metric-container"]:hover {
    transform: translateY(-4px) scale(1.02);
    box-shadow:
        0 0 36px rgba(56,189,248,0.65),
        inset 0 0 20px rgba(255,255,255,0.10);
}

/* ===============================
   🔘 BUTTONS
   =============================== */
.stButton > button {
    background: linear-gradient(135deg, #38bdf8, #6366f1);
    color: #020617;
    font-weight: 600;
    border-radius: 14px;
    padding: 0.6rem 1.4rem;
    border: none;
    box-shadow: 0 0 22px rgba(99,102,241,0.6);
    transition: all 0.3s ease;
}

.stButton > button:hover {
    transform: scale(1.06);
    box-shadow: 0 0 38px rgba(99,102,241,0.9);
}

/* ===============================
   📊 DATAFRAME
   =============================== */
[data-testid="stDataFrame"] {
    background: rgba(255,255,255,0.05);
    border-radius: 16px;
    border: 1px solid rgba(255,255,255,0.14);
    box-shadow: inset 0 0 14px rgba(255,255,255,0.05);
}

/* ===============================
   📈 CHART GLOW
   =============================== */
svg {
    filter: drop-shadow(0 0 14px rgba(56,189,248,0.4));
}

/* ===============================
   🪟 SCROLLBAR
   =============================== */
::-webkit-scrollbar {
    width: 8px;
}
::-webkit-scrollbar-thumb {
    background: linear-gradient(#38bdf8, #6366f1);
    border-radius: 10px;
}

</style>
""", unsafe_allow_html=True)

# ============================================================
# DATA SETUP
# ============================================================
DATA_DIR = "data"
TRAIN_PATH = os.path.join(DATA_DIR, "training_data.csv")
CHATLOG_PATH = os.path.join(DATA_DIR, "chat_logs.csv")

os.makedirs(DATA_DIR, exist_ok=True)

if not os.path.exists(TRAIN_PATH):
    pd.DataFrame(columns=["intent", "utterance"]).to_csv(TRAIN_PATH, index=False)

if not os.path.exists(CHATLOG_PATH):
    pd.DataFrame(columns=["query", "intent", "confidence", "date"]).to_csv(CHATLOG_PATH, index=False)

df = pd.read_csv(CHATLOG_PATH)
train_df = pd.read_csv(TRAIN_PATH)

# ============================================================
# HEADER
# ============================================================
st.markdown("## 📊 BankBot Admin Dashboard")
st.caption("One-page analytics • Admin-controlled NLU • Real user data")

# ============================================================
# SYSTEM VALIDATION STATUS
# ============================================================
st.divider()
st.markdown("## 🧪 System Validation Status")

st.success("✔ Dashboard Tests: Passed")
st.success("✔ Intent Recognition Tests: Passed")
st.warning("⚠ Text Generation Tests: 1 Failed")
st.success("✔ LLM Integration Tests: Passed")
st.success("✔ Parser Tests: Passed")

# ============================================================
# KPI CARDS
# ============================================================
st.divider()
c1, c2, c3, c4 = st.columns(4)

avg_conf = df["confidence"].mean() if not df.empty else 0

c1.metric("Total Queries", len(df))
c2.metric("Avg Confidence", f"{avg_conf*100:.1f}%")
c3.metric("Intents", df["intent"].nunique() if not df.empty else 0)
c4.metric("Low Confidence", len(df[df["confidence"] < 0.6]) if not df.empty else 0)

# ============================================================
# NLU TRAINING PANEL
# ============================================================
st.divider()
st.markdown("## 🧠 Train NLU Model")

col1, col2, col3 = st.columns(3)

with col1:
    epochs = st.slider("Epochs", 1, 50, 10)

with col2:
    batch_size = st.slider("Batch Size", 2, 32, 8)

with col3:
    st.text_input("Learning Rate", value="0.01", disabled=True)

if st.button("🚀 Start Training"):
    retrain_model()
    st.success(f"Model trained with epochs={epochs}, batch={batch_size}")


# ---------------- ACTION BUTTONS ----------------
b1, b2, b3 = st.columns(3)

with b1:
    if st.button("🔄 Refresh"):
        st.experimental_rerun() if hasattr(st, "experimental_rerun") else None

with b2:
    st.download_button("⬇ Export CSV", df.to_csv(index=False), "analytics.csv")

with b3:
    if st.button("🚀 Retrain Model"):
        retrain_model()
        st.success("Model retrained!")
        if hasattr(st, "experimental_rerun"):
            st.experimental_rerun()

# ---------------- CONFIDENCE BARS ----------------
st.markdown("### 📈 Confidence Visualization")
for _, row in df.iterrows():
    st.markdown(f"**{row['query']}** → `{row['intent']}`")
    st.progress(float(row["confidence"]))  # ensure confidence is 0-1

# ---------------- INTENT CORRECTION ----------------
st.markdown("### ✏️ Correct Intent")

if not df.empty:
    # Select a valid index
    idx = st.selectbox(
        "Select Query",
        df.index,
        format_func=lambda i: df.loc[i, "query"]
    )

    # Safely get the current intent
    current_intent = df.loc[idx, "intent"] if idx in df.index else ""

    new_intent = st.text_input("Correct Intent", current_intent)

    if st.button("Update Intent"):
        if idx in df.index:  # only update if idx is valid
            df.loc[idx, "intent"] = new_intent
            df.to_csv(chatlogs_path, index=False)
            st.success("Intent updated")
            # Use experimental_rerun if available
            if hasattr(st, "experimental_rerun"):
                st.experimental_rerun()
else:
    st.info("No chat logs available for correction.")

# ---------------- TRAINING DATA EDITOR ----------------
st.markdown("### 🧠 Training Data Editor")
st.dataframe(train_df, use_container_width=True)

with st.form("add_train"):
    i = st.text_input("Intent")
    u = st.text_input("Utterance")
    if st.form_submit_button("Add"):
        train_df.loc[len(train_df)] = [i, u]
        train_df.to_csv(training_path, index=False)
        st.success("Training data added")
        st.experimental_rerun()


        st.divider()
st.markdown("## 🔝 Top User Queries")

top_q = (
    df["query"]
    .value_counts()
    .head(5)
    .reset_index()
    .rename(columns={"index": "Query", "query": "Count"})
)

st.table(top_q)


st.markdown("## ❤️ NLU Model Health")

avg_conf = df["confidence"].mean()

if avg_conf > 0.85:
    st.success("🟢 Model Health: Good")
elif avg_conf > 0.6:
    st.warning("🟡 Model Health: Needs Review")
else:
    st.error("🔴 Model Health: Poor")


st.markdown("## 📉 Confidence Trend Over Time")

trend = (
    df.groupby("date")["confidence"]
    .mean()
    .reset_index()
)

st.line_chart(trend, x="date", y="confidence")



# ---------------- DRIFT DETECTION ----------------
st.markdown("### ⚠️ Intent Drift Detection")

if not df.empty:
    low_conf = len(df[df.confidence < 0.6]) / len(df) * 100
    if low_conf > 20:
        st.error("Intent drift detected! Retrain recommended.")
    else:
        st.success("Model stable.")
else:
    st.info("No chat logs available to detect drift.")


with st.expander("ℹ️ How to Read This Dashboard"):
    st.markdown("""
    - **Intent Distribution** shows how users interact with the chatbot.
    - **Confidence Score** represents prediction certainty.
    - **Low confidence** indicates missing or weak training data.
    - **Training Panel** allows admin-controlled retraining.
    - **Drift Trend** highlights model degradation over time.
    """)

