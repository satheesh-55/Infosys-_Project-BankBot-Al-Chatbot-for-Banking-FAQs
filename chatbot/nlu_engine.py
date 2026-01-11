import pandas as pd
import json
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
TRAIN_PATH = BASE_DIR / "data" / "training_data.csv"
TRAIN_PATH = "data/training_data.csv"
ENTITY_PATH = "data/entity_patterns.json"

# Global model state
vectorizer = None
X = None
labels = None
utterances = None

# --------------------------------------------------
# LOAD / RETRAIN MODEL
# --------------------------------------------------
def load_nlu_model():
    df = pd.read_csv(TRAIN_PATH)
    return df

    if df.empty:
        vectorizer = None
        X = None
        labels = None
        utterances = None
        return

    utterances = df["utterance"].tolist()
    labels = df["intent"].tolist()

    vectorizer = TfidfVectorizer()
    X = vectorizer.fit_transform(utterances)


# --------------------------------------------------
# ENTITY EXTRACTION
# --------------------------------------------------
def extract_entities(text):
    with open(ENTITY_PATH) as f:
        patterns = json.load(f)

    entities = {}

    for entity, pattern in patterns.items():
        match = re.findall(pattern, text.lower())
        if match:
            entities[entity] = match

    return entities


# --------------------------------------------------
# INTENT PREDICTION
# --------------------------------------------------
def predict_intent(text):
    if vectorizer is None:
        return "unknown", 0.0, {}

    text_vec = vectorizer.transform([text])
    similarities = cosine_similarity(text_vec, X)[0]

    best_idx = similarities.argmax()
    confidence = float(similarities[best_idx])
    intent = labels[best_idx]

    entities = extract_entities(text)

    return intent, confidence, entities


# Load model initially
load_nlu_model()
