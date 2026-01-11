import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
import os


MODEL_PATH = "models/intent_model.pkl"


class IntentClassifier:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            stop_words="english"
        )
        self.model = LogisticRegression(
            max_iter=1000,
            solver="lbfgs",
            multi_class="auto"
        )

    def train(self, texts, labels):
        X = self.vectorizer.fit_transform(texts)
        self.model.fit(X, labels)

        os.makedirs("models", exist_ok=True)
        joblib.dump(
            (self.vectorizer, self.model),
            MODEL_PATH
        )

    def predict(self, text):
        if not os.path.exists(MODEL_PATH):
            return "llm_fallback", 0.0

        vectorizer, model = joblib.load(MODEL_PATH)
        X = vectorizer.transform([text])

        probabilities = model.predict_proba(X)[0]
        confidence = float(max(probabilities))
        intent = model.classes_[probabilities.argmax()]

        return intent, confidence



 
