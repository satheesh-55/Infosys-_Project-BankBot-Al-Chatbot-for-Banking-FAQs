import os
import json
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

class IntentClassifier:
    def __init__(self, model_path):
        self.model_path = model_path

        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_path,
            local_files_only=True
        )

        # Load model
        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_path,
            local_files_only=True
        )

        # Load id2label.json
        labels_file = os.path.join(model_path, "id2label.json")  # use id2label.json
        with open(labels_file, "r") as f:
            self.id2label = json.load(f)  # keys are strings

    def predict_intent(self, text):
        """Returns predicted intent label string and confidence"""

        # Tokenize input
        tokens = self.tokenizer(text, return_tensors="pt", truncation=True, padding=True)

        # Predict
        with torch.no_grad():
            outputs = self.model(**tokens)
            logits = outputs.logits
            predicted_class_id = torch.argmax(logits).item()
            confidence = torch.softmax(logits, dim=1)[0, predicted_class_id].item()

        # Map to label using id2label
        predicted_intent = self.id2label[str(predicted_class_id)]

        return predicted_intent, confidence