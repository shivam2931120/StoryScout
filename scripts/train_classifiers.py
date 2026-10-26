"""Run a reproducible, leakage-safe multi-label genre classification experiment."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
import sys

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import MultiLabelBinarizer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.config import ARTIFACT_DIR
from src.data_loader import load_active_catalogs


def experiment(items, min_train_support: int = 20) -> dict:
    train, test = train_test_split(items, test_size=0.2, random_state=42)
    train_counts = Counter(genre for item in train for genre in item.genres)
    labels = sorted(label for label, count in train_counts.items() if count >= min_train_support)
    if len(train) < 40 or not labels:
        return {"status": "skipped", "record_count": len(items), "reason": "Insufficient labeled records after the fixed training-only rare-label cutoff."}

    binarizer = MultiLabelBinarizer(classes=labels)
    y_train = binarizer.fit_transform([item.genres for item in train])
    y_test = binarizer.transform([[genre for genre in item.genres if genre in labels] for item in test])
    # Titles only: never append the genre labels to the input text.
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), strip_accents="unicode", min_df=2, sublinear_tf=True)
    x_train = vectorizer.fit_transform([item.title for item in train])
    x_test = vectorizer.transform([item.title for item in test])
    model = OneVsRestClassifier(LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42))
    model.fit(x_train, y_train)
    prediction = model.predict(x_test)
    metrics = classification_report(y_test, prediction, target_names=labels, output_dict=True, zero_division=0)
    per_label = {label: {"train_support": int(train_counts[label]), "test_support": int(y_test[:, index].sum()), "precision": round(metrics[label]["precision"], 4), "recall": round(metrics[label]["recall"], 4), "f1": round(metrics[label]["f1-score"], 4)} for index, label in enumerate(labels)}
    return {
        "status": "measured",
        "records": len(items), "train_records": len(train), "test_records": len(test),
        "input_fields": ["title"], "random_state": 42, "test_fraction": 0.2,
        "rare_label_threshold_training_support": min_train_support,
        "labels": per_label,
        "micro_avg": {key: round(metrics["micro avg"][key], 4) for key in ("precision", "recall", "f1-score")},
        "macro_avg": {key: round(metrics["macro avg"][key], 4) for key in ("precision", "recall", "f1-score")},
        "weighted_avg": {key: round(metrics["weighted avg"][key], 4) for key in ("precision", "recall", "f1-score")},
        "limitations": "MovieLens genres are coarse source labels. The title-only input is intentionally conservative, excludes genre/tag fields, and is not used by the live recommender. Train-only support filtering can omit rare labels from held-out scores.",
    }


def main() -> None:
    result = {}
    for media, items in load_active_catalogs().items():
        result[media] = experiment(items)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    target = ARTIFACT_DIR / "genre_classifier_results.json"
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
