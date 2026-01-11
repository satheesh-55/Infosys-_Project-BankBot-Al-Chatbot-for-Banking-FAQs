# nlu_ui_dashboard_full.py
import streamlit as st
import os
import json
import re
from nlu_engine.intent_classifier import IntentClassifier
from nlu_engine.entity_extractor import get_entities
from nlu_engine.train_intent import train

# ----------------------------
# Paths
# ----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INTENT_MODEL_PATH = os.path.join(BASE_DIR, "models", "intent_model")
TRAIN_DATA_PATH = os.path.join(BASE_DIR, "nlu_engine", "intents.json")

# ----------------------------
# Load Intent Classifier
# ----------------------------
classifier = IntentClassifier(model_path=INTENT_MODEL_PATH)

# ----------------------------
# Streamlit Layout
# ----------------------------
st.set_page_config(page_title="BankBot NLU Dashboard", layout="wide")
st.title("💬 BankBot NLU Visualizer & Trainer")

# ----------------------------
# Helper: Highlight Entities
# ----------------------------
def highlight_entities(text, entities):
    colors = {
        "amount": "#28a745",
        "from_account": "#17a2b8",
        "to_account": "#ffc107",
        "account_number": "#007bff",
        "transaction_id": "#6f42c1",
        "date": "#fd7e14",
        "account_type": "#e83e8c"
    }
    safe_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    for ent_type, color in colors.items():
        for val in entities.get(ent_type, []):
            safe_val = val.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            safe_text = re.sub(
                re.escape(safe_val),
                f'<span style="color:{color}; font-weight:bold">{safe_val}</span>',
                safe_text
            )
    return safe_text

# ----------------------------
# User Input Section
# ----------------------------
st.subheader("NLU Engine in Action")
user_query = st.text_input(
    "User Query:", 
    placeholder="I want to transfer 5000 rupees from my savings account to checking account 4532"
)

top_k = st.number_input("Top intents to show", min_value=1, max_value=5, value=4)

if st.button("Analyze"):
    if not user_query.strip():
        st.warning("Please enter a query!")
    else:
        # 1️⃣ Predict top intents (workaround if classifier only has predict)
        predicted_intent, confidence = classifier.predict(user_query)
        top_intents = [(predicted_intent, confidence)]  # single intent as top

        # 2️⃣ Extract entities
        entities = get_entities(user_query)

        # 3️⃣ Highlight entities in text
        highlighted_text = highlight_entities(user_query, entities)

        # ----------------------------
        # Display Results
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Predicted Intents (sorted by confidence)")
            for idx, (intent, conf) in enumerate(top_intents):
                st.write(f"{idx+1}. **{intent}** — Confidence: {conf:.4f}")
                st.progress(int(conf * 100))

            st.subheader("Extracted Entities")
            entity_list = []
            for ent_type, values in entities.items():
                for i, val in enumerate(values, 1):
                    entity_list.append({"entity": val, "label": ent_type, "index": i})
            st.table(entity_list)

            st.subheader("Highlighted Query Text")
            st.markdown(highlighted_text, unsafe_allow_html=True)

        with col2:
            st.subheader("Edit or Add Intents")
            if os.path.exists(TRAIN_DATA_PATH):
                with open(TRAIN_DATA_PATH, "r") as f:
                    intents_data = json.load(f)
            else:
                intents_data = {}

            st.markdown("### Existing Intents:")
            selected_intent = st.selectbox(
                "Select intent to view/edit examples",
                list(intents_data.keys()) if intents_data else []
            )

            if selected_intent:
                examples = intents_data[selected_intent]
                new_examples = st.text_area("Examples (one per line)", "\n".join(examples))
                if st.button("Save changes to existing intent"):
                    intents_data[selected_intent] = [
                        ex.strip() for ex in new_examples.split("\n") if ex.strip()
                    ]
                    with open(TRAIN_DATA_PATH, "w") as f:
                        json.dump(intents_data, f, indent=2)
                    st.success(f"Intent '{selected_intent}' updated!")

            st.markdown("### Create New Intent")
            new_intent_name = st.text_input("Intent Name")
            new_intent_examples = st.text_area("Examples (one per line)")
            if st.button("Add Intent"):
                if new_intent_name.strip() and new_intent_examples.strip():
                    intents_data[new_intent_name.strip()] = [
                        ex.strip() for ex in new_intent_examples.split("\n") if ex.strip()
                    ]
                    with open(TRAIN_DATA_PATH, "w") as f:
                        json.dump(intents_data, f, indent=2)
                    st.success(f"Intent '{new_intent_name}' added!")

# ----------------------------
# Model Training Section
# ----------------------------
st.subheader("⚙ Train Intent Classifier")
epochs = st.number_input("Epochs", min_value=1, max_value=20, value=10)
batch_size = st.number_input("Batch Size", min_value=2, max_value=32, value=8)
learning_rate = st.number_input(
    "Learning Rate", min_value=0.00001, max_value=0.01, value=0.00003, format="%.5f"
)

if st.button("Train Model"):
    with st.spinner("Training model... this may take a few minutes..."):
        train(TRAIN_DATA_PATH, INTENT_MODEL_PATH, epochs, batch_size, learning_rate)
    st.success("Model training completed!")
    st.balloons()