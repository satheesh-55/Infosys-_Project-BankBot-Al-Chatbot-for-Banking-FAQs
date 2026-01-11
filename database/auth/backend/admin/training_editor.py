import streamlit as st
import pandas as pd
from backend.nlu.intent_classifier import IntentClassifier

st.subheader("Create New Intent")

intent = st.text_input("Intent Name")
examples = st.text_area("Examples (one per line)")

if st.button("Save & Train"):
    lines = examples.split("\n")
    df = pd.DataFrame({"text": lines, "intent": intent})
    df.to_csv("data/training_data.csv", mode="a", header=False, index=False)

    data = pd.read_csv("data/training_data.csv")
    clf = IntentClassifier()
    clf.train(data["text"], data["intent"])
    st.success("Model trained successfully")
