import os
import logging
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logging.basicConfig(level=logging.INFO)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRAIN_PATH = os.path.join(BASE_DIR, "data", "training_data.csv")


class IntentEngine:
    def __init__(self, threshold: float = 0.3):
        self.vectorizer = None
        self.matrix = None
        self.labels = []
        self.threshold = threshold

    def load_model(self):
        df = pd.read_csv(TRAIN_PATH)

        df = df.dropna()
        df["utterance"] = df["utterance"].str.lower().str.strip()
        df["intent"] = df["intent"].str.lower().str.strip()

        self.labels = df["intent"].tolist()
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.matrix = self.vectorizer.fit_transform(df["utterance"])

        logging.info("Intent model loaded successfully")

    def predict(self, query: str):
        if not query.strip():
            return "unknown", 0.0

        vec = self.vectorizer.transform([query.lower()])
        sims = cosine_similarity(vec, self.matrix)[0]
        idx = sims.argmax()
        score = float(sims[idx])

        if score < self.threshold:
            return "unknown", score

        return self.labels[idx], score


# ✅ SINGLE GLOBAL ENGINE (IMPORTANT)
engine = IntentEngine()
engine.load_model()
