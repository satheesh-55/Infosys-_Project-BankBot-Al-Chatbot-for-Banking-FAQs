import streamlit as st
import pandas as pd
from sqlalchemy import text
from backend.database import engine
import plotly.express as px

st.divider()
st.subheader("📌 Intent Distribution")

if total_queries > 0:
    intent_fig = px.pie(
        df,
        names="predicted_intent",
        title="Intent Usage Distribution"
    )
    st.plotly_chart(intent_fig, use_container_width=True)
else:
    st.info("No data available")


# ---------- PAGE CONFIG ----------
st.set_page_config(
    page_title="BankBot Admin Dashboard",
    layout="wide"
)

st.title("📊 BankBot Admin Dashboard")

# ---------- LOAD DATA ----------
query = """
SELECT
    user_query,
    predicted_intent,
    confidence,
    success,
    timestamp
FROM chat_logs
ORDER BY timestamp DESC
"""

df = pd.read_sql(text(query), engine)

# ---------- KPI CALCULATIONS ----------
total_queries = len(df)

success_rate = (
    (df["success"].sum() / total_queries) * 100
    if total_queries > 0 else 0
)

avg_confidence = (
    df["confidence"].mean()
    if total_queries > 0 else 0
)

# ---------- KPI DISPLAY ----------
col1, col2, col3 = st.columns(3)

col1.metric(
    label="Total Queries",
    value=total_queries
)

col2.metric(
    label="Success Rate",
    value=f"{success_rate:.2f}%"
)

col3.metric(
    label="Average Confidence",
    value=f"{avg_confidence:.2f}"
)

st.divider()

# ---------- RECENT CHAT ACTIVITY ----------
st.subheader("🕒 Recent Chat Activity")

st.dataframe(
    df,
    use_container_width=True,
    height=350
)

st.subheader("📈 Confidence Distribution")

if total_queries > 0:
    conf_fig = px.histogram(
        df,
        x="confidence",
        nbins=10,
        title="Confidence Score Distribution"
    )
    st.plotly_chart(conf_fig, use_container_width=True)
else:
    st.info("No data available")

