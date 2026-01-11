import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="🏦 Bankbot Admin",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🏦 Bank Chatbot Command Center")
st.markdown("---")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Queries", 12450, delta="+24")
with col2:
    st.metric("Success Rate", "88.5%", delta="+4.2%")
with col3:
    st.metric("Avg Response", "245ms", delta="-15ms")

st.success("✅ Bankbot is running!")
