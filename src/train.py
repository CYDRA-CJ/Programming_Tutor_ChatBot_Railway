# train.py — trains Logistic Regression, Linear SVM, and MLP/ANN intent classifiers.
# All three models use TF-IDF preprocessing inside a scikit-learn Pipeline.
# MLP is the required production model; it is always promoted to models/classifier.joblib.
# Run from project root: .\.venv\Scripts\python.exe src\train.py

import csv, io, json, os, re, shutil, time
from collections import Counter
from datetime import datetime

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

TRAIN_CSV   = os.path.join("data", "splits", "train.csv")
VAL_CSV     = os.path.join("data", "splits", "val.csv")
RESULTS_DIR = os.path.join("results", "training")
BEST_DIR    = os.path.join("models")

# 7-column schema (review_status removed)
FIELDNAMES = [
    "text", "intents", "primary_intent", "topic_tags",
    "language_tags", "source_group", "context_required",
]

# 11 approved intents
APPROVED_INTENTS = [
    "greeting", "bot_capabilities", "explain_concept", "show_syntax",
    "show_example", "generate_code", "explain_code",
    "compare_concepts", "request_quiz", "follow_up", "clarification",
]

RANDOM_SEED = 42

# TF-IDF: unigrams + bigrams, max 20k features, log-scaled term frequencies
TFIDF_PARAMS = {
    "ngram_range":   (1, 2),
    "max_features":  20_000,
    "sublinear_tf":  True,
    "min_df":        1,
    "strip_accents": "unicode",
    "analyzer":      "word",
    "token_pattern": r"(?u)\b\w+\b",
}

# Three models: two baselines + the required ANN
MODEL_CONFIGS = {
    "lr": {
        "name":       "Logistic Regression (Baseline)",
        "filename":   "lr_model.joblib",
        "classifier": LogisticRegression(
            max_iter=1000, C=1.0, solver="lbfgs", random_state=RANDOM_SEED),
    },
    "svm": {
        "name":       "Linear SVM (Baseline)",
        "filename":   "svm_model.joblib",
        "classifier": LinearSVC(
            max_iter=2000, C=1.0, random_state=RANDOM_SEED),
    },
    "mlp": {
        "name":       "MLP / ANN (Required)",
        "filename":   "mlp_model.joblib",
        "classifier": MLPClassifier(
            hidden_layer_sizes=(256, 128),
            activation="relu",
            solver="adam",
            alpha=1e-4,
            learning_rate_init=1e-3,
            max_iter=300,
            early_stopping=True,
            validation_fraction=0.1,
            n_iter_no_change=15,
            random_state=RANDOM_SEED,
            verbose=False,
        ),
    },
}


def normalise(text):
    # Lowercase and collapse whitespace — must match evaluate.py exactly
    return re.sub(r"\s+", " ", text.lower()).strip()


def load_split(path):
    # Load (texts, labels) from a split CSV, skipping unknown intents
    texts, labels = [], []
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith('"text"') or line.startswith("text,"):
            continue
        try:
            parsed = next(csv.reader(io.StringIO(line)))
        except StopIteration:
            continue
        if len(parsed) < 7:
            continue
        row    = dict(zip(FIELDNAMES, parsed[:7]))
        intent = row["primary_intent"].strip().strip('"')
        if intent not in APPROVED_INTENTS:
            continue
        texts.append(normalise(row["text"]))
        labels.append(intent)
    return texts, labels


def next_run_id():
    # Auto-increment run ID: train_001, train_002, ...
    os.makedirs(RESULTS_DIR, exist_ok=True)
    existing = [d for d in os.listdir(RESULTS_DIR)
                if os.path.isdir(os.path.join(RESULTS_DIR, d))
                and re.match(r"^train_\d+$", d)]
    if not existing:
        return "train_001"
    return f"train_{max(int(d.split('_')[1]) for d in existing) + 1:03d}"


def train_model(key, config, X_train, y_train, X_val, y_val):
    # Build TF-IDF + classifier pipeline, fit on train, score on val
    print(f"\n  Training: {config['name']} ...")
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(**TFIDF_PARAMS)),
        ("clf",   config["classifier"]),
    ])
    start = time.time()
    pipeline.fit(X_train, y_train)
    train_time = time.time() - start
    y_pred  = pipeline.predict(X_val)
    val_acc = accuracy_score(y_val, y_pred)
    val_f1  = f1_score(y_val, y_pred, average="macro", zero_division=0)
    val_rep = classification_report(y_val, y_pred,
                                    labels=APPROVED_INTENTS, zero_division=0)
    print(f"    Train time : {train_time:.1f}s")
    print(f"    Val Acc    : {val_acc:.4f}  ({val_acc*100:.2f}%)")
    print(f"    Val Macro-F1: {val_f1:.4f}")
    return {
        "key": key, "name": config["name"], "filename": config["filename"],
        "pipeline": pipeline, "train_time": round(train_time, 2),
        "val_acc": round(val_acc, 4), "val_f1": round(val_f1, 4),
        "val_report": val_rep,
    }


def save_artifacts(run_dir, results, run_id, timestamp, best_key):
    os.makedirs(run_dir, exist_ok=True)
    for res in results:
        path = os.path.join(run_dir, res["filename"])
        joblib.dump(res["pipeline"], path)
        print(f"    Saved: {path}")

    metadata = {
        "run_id": run_id, "timestamp": timestamp,
        "random_seed": RANDOM_SEED, "tfidf_params": TFIDF_PARAMS,
        "models": {
            res["key"]: {
                "name": res["name"], "filename": res["filename"],
                "train_time": res["train_time"],
                "val_accuracy": res["val_acc"], "val_macro_f1": res["val_f1"],
            } for res in results
        },
        "best_model": best_key, "train_csv": TRAIN_CSV, "val_csv": VAL_CSV,
    }
    with open(os.path.join(run_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    # Human-readable training summary
    lines = ["=" * 72, "TRAINING REPORT",
             f"Run ID    : {run_id}", f"Timestamp : {timestamp}",
             f"Train CSV : {TRAIN_CSV}", f"Val CSV   : {VAL_CSV}",
             f"Seed      : {RANDOM_SEED}", "=" * 72]
    for res in results:
        lines += ["", "─" * 72, f"Model     : {res['name']}",
                  f"Val Acc   : {res['val_acc']:.4f}",
                  f"Val Macro-F1: {res['val_f1']:.4f}", "",
                  "Per-intent classification report (validation set):",
                  res["val_report"]]
    lines += ["=" * 72, f"BEST MODEL ON VALIDATION: {best_key.upper()}", "=" * 72]
    report = "\n".join(lines)
    with open(os.path.join(run_dir, "training_report.txt"), "w", encoding="utf-8") as f:
        f.write(report)
    return report


def promote_best(run_dir, best_result, run_id):
    # Copy the MLP (production model) to models/classifier.joblib for Flask
    os.makedirs(BEST_DIR, exist_ok=True)
    src = os.path.join(run_dir, best_result["filename"])
    dst = os.path.join(BEST_DIR, "classifier.joblib")
    shutil.copy2(src, dst)
    meta = {
        "source_run": run_id, "model_name": best_result["name"],
        "val_accuracy": best_result["val_acc"], "val_macro_f1": best_result["val_f1"],
        "promoted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "load_path": dst,
    }
    with open(os.path.join(BEST_DIR, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"\n  Best model promoted → {dst}")


def main():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_id    = next_run_id()
    run_dir   = os.path.join(RESULTS_DIR, run_id)

    print("=" * 72)
    print(f"  TRAINING RUN : {run_id}")
    print(f"  Timestamp    : {timestamp}")
    print("=" * 72)

    print(f"\nLoading training data from  : {TRAIN_CSV}")
    X_train, y_train = load_split(TRAIN_CSV)
    print(f"  Train rows  : {len(X_train)}")
    print(f"  Intent dist : {dict(sorted(Counter(y_train).items()))}")

    print(f"\nLoading validation data from: {VAL_CSV}")
    X_val, y_val = load_split(VAL_CSV)
    print(f"  Val rows    : {len(X_val)}")

    print("\nTraining models ...")
    results = [train_model(k, c, X_train, y_train, X_val, y_val)
               for k, c in MODEL_CONFIGS.items()]

    best_result = max(results, key=lambda r: r["val_f1"])
    best_key    = best_result["key"]

    print("\n" + "─" * 72)
    print("Validation Summary:")
    print(f"  {'Model':<35} {'Acc':>8} {'Macro-F1':>10}")
    print("  " + "-" * 54)
    for res in results:
        marker = " ← BEST" if res["key"] == best_key else ""
        print(f"  {res['name']:<35} {res['val_acc']:>8.4f} {res['val_f1']:>10.4f}{marker}")

    print(f"\nSaving artifacts to: {run_dir}")
    save_artifacts(run_dir, results, run_id, timestamp, best_key)

    # Always promote MLP to models/ — it is the required production model
    mlp_result    = next((r for r in results if r["key"] == "mlp"), best_result)
    promote_best(run_dir, mlp_result, run_id)

    print("\n" + "=" * 72)
    print(f"  Run complete  : {run_id}")
    print(f"  Artifacts     : {run_dir}")
    print(f"  Best model    : {best_key.upper()} (val macro-F1 = {best_result['val_f1']:.4f})")
    print(f"  Best model →  : {os.path.join(BEST_DIR, 'classifier.joblib')}")
    print("=" * 72)
    print(f"\nTo evaluate on the test set run:")
    print(f"  .venv/Scripts/python.exe src/evaluate.py --run {run_id}")


if __name__ == "__main__":
    main()
