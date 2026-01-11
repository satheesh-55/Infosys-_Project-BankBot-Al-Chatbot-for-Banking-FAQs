import json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

MODEL = None
VECTORIZER = None
INTENTS = None


def load_model():
    global MODEL, VECTORIZER, INTENTS

    with open("intents.json") as f:
        INTENTS = json.load(f)

    X, y = [], []
    for intent, examples in INTENTS.items():
        for ex in examples:
            X.append(ex)
            y.append(intent)

    VECTORIZER = TfidfVectorizer()
    X_vec = VECTORIZER.fit_transform(X)

    MODEL = LogisticRegression()
    MODEL.fit(X_vec, y)


def predict_intent(text: str):
    if MODEL is None:
        load_model()

    X = VECTORIZER.transform([text])
    probs = MODEL.predict_proba(X)[0]
    intent = MODEL.classes_[probs.argmax()]
    confidence = round(probs.max() * 100, 2)

    return intent, confidence
