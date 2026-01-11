import streamlit as st
import pandas as pd
import plotly.express as px
from backend.database import SessionLocal, ChatLog

db = SessionLocal()
logs = pd.read_sql("chat_logs", db.bind)

st.subheader("Intent Distribution")
fig = px.pie(logs, names="predicted_intent")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Confidence Distribution")
fig2 = px.histogram(logs, x="confidence")
st.plotly_chart(fig2, use_container_width=True)
