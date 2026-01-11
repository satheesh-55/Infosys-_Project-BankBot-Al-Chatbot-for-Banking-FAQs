# train_intent.py

import json
import os
from transformers import AutoTokenizer, AutoModelForSequenceClassification, TrainingArguments, Trainer
from datasets import Dataset
import torch

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "models", "intent_model")

def load_training_data(data_path):
    with open(data_path, "r") as f:
        intents = json.load(f)

    texts = []
    labels = []
    label_map = {intent: idx for idx, intent in enumerate(intents.keys())}

    for intent, examples in intents.items():
        for ex in examples:
            texts.append(ex)
            labels.append(label_map[intent])

    return texts, labels, label_map


def train(data_path, model_path, epochs, batch_size, learning_rate):
    print("📌 Loading training data...")
    texts, labels, label_map = load_training_data(data_path)

    dataset = Dataset.from_dict({
        "text": texts,
        "label": labels
    })

    print("📌 Loading tokenizer & model...")
    tokenizer = AutoTokenizer.from_pretrained("distilbert-base-uncased")

    def tokenize(batch):
        return tokenizer(batch["text"], padding=True, truncation=True)

    dataset = dataset.map(tokenize, batched=True)

    model = AutoModelForSequenceClassification.from_pretrained(
        "distilbert-base-uncased",
        num_labels=len(label_map)
    )

    training_args = TrainingArguments(
        output_dir=model_path,
        evaluation_strategy="no",
        per_device_train_batch_size=batch_size,
        num_train_epochs=epochs,
        learning_rate=learning_rate,
        logging_steps=10,
        save_total_limit=1
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset
    )

    print("📌 Training started...")
    trainer.train()
    print("✅ Training complete!")

    print("📌 Saving model & labels...")
    os.makedirs(model_path, exist_ok=True)

    model.save_pretrained(model_path)
    tokenizer.save_pretrained(model_path)

    with open(os.path.join(model_path, "labels.json"), "w") as f:
        json.dump(label_map, f, indent=2)

    print("🎉 Model saved successfully!")
