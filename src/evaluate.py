# evaluate.py — evaluates a saved training run against the held-out test set.
# The test set is used ONLY here — never during training or threshold tuning.
# Run from project root: .\.venv\Scripts\python.exe src\evaluate.py --run train_001

import argparse, csv, io, json, os, re
from collections import Counter
from datetime import datetime

import joblib
import numpy as np
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix, f1_score,
)

# Optional: confusion matrix plots (skipped silently if matplotlib not installed)
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

TEST_CSV     = os.path.join("data", "splits", "test.csv")
TRAINING_DIR = os.path.join("results", "training")
EVAL_DIR     = os.path.join("results", "evaluation")

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

MODEL_FILES = {
    "lr_model.joblib":  "Logistic Regression (Baseline)",
    "svm_model.joblib": "Linear SVM (Baseline)",
    "mlp_model.joblib": "MLP / ANN (Required)",
}


def normalise(text):
    # Must match train.py normalise() exactly
    return re.sub(r"\s+", " ", text.lower()).strip()


def load_test():
    # Load test split — never touched during training
    texts, labels = [], []
    if not os.path.exists(TEST_CSV):
        raise FileNotFoundError(
            f"Test CSV not found: {TEST_CSV}\n"
            "Run scripts/split_dataset.py first.")
    with open(TEST_CSV, "r", encoding="utf-8") as f:
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


def save_confusion_matrix(cm, labels, title, path):
    if not HAS_MATPLOTLIB:
        return None
    fig, ax = plt.subplots(figsize=(14, 12))
    im = ax.imshow(cm, interpolation="nearest", cmap=plt.cm.Blues)
    plt.colorbar(im, ax=ax)
    ax.set(xticks=np.arange(len(labels)), yticks=np.arange(len(labels)),
           xticklabels=labels, yticklabels=labels,
           title=title, ylabel="True label", xlabel="Predicted label")
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=8)
    plt.setp(ax.get_yticklabels(), fontsize=8)
    thresh = cm.max() / 2.0
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center",
                    fontsize=7, color="white" if cm[i, j] > thresh else "black")
    fig.tight_layout()
    plt.savefig(path, dpi=100)
    plt.close(fig)
    return path


def next_eval_id():
    # Auto-increment eval ID: eval_001, eval_002, ...
    os.makedirs(EVAL_DIR, exist_ok=True)
    existing = [d for d in os.listdir(EVAL_DIR)
                if os.path.isdir(os.path.join(EVAL_DIR, d))
                and re.match(r"^eval_\d+$", d)]
    if not existing:
        return "eval_001"
    return f"eval_{max(int(d.split('_')[1]) for d in existing) + 1:03d}"


def evaluate_model(model_file, display_name, pipeline, X_test, y_test, eval_run_dir):
    key    = model_file.replace("_model.joblib", "")
    y_pred = pipeline.predict(X_test)
    acc    = accuracy_score(y_test, y_pred)
    f1     = f1_score(y_test, y_pred, average="macro", zero_division=0)
    report = classification_report(y_test, y_pred,
                                   labels=APPROVED_INTENTS, zero_division=0)
    cm     = confusion_matrix(y_test, y_pred, labels=APPROVED_INTENTS)

    print(f"\n  {display_name}")
    print(f"    Test Accuracy   : {acc:.4f}  ({acc*100:.2f}%)")
    print(f"    Test Macro-F1   : {f1:.4f}")

    cm_path = None
    if HAS_MATPLOTLIB:
        cm_path = os.path.join(eval_run_dir, f"confusion_matrix_{key}.png")
        save_confusion_matrix(cm, APPROVED_INTENTS,
                              f"Confusion Matrix — {display_name}", cm_path)
        print(f"    Confusion matrix → {cm_path}")

    return {
        "key": key, "name": display_name,
        "accuracy": round(acc, 4), "macro_f1": round(f1, 4),
        "report": report, "cm": cm.tolist(), "cm_path": cm_path,
    }


def save_eval_artifacts(eval_run_dir, eval_id, run_id, results, timestamp):
    os.makedirs(eval_run_dir, exist_ok=True)

    # Save metrics as JSON for programmatic access
    metrics = {
        "eval_id": eval_id, "training_run": run_id,
        "timestamp": timestamp, "test_csv": TEST_CSV,
        "models": {
            r["key"]: {"name": r["name"], "accuracy": r["accuracy"],
                       "macro_f1": r["macro_f1"], "cm_path": r["cm_path"]}
            for r in results
        },
    }
    with open(os.path.join(eval_run_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    best = max(results, key=lambda r: r["macro_f1"])
    lines = ["=" * 72, "EVALUATION REPORT",
             f"Eval ID      : {eval_id}", f"Training Run : {run_id}",
             f"Timestamp    : {timestamp}", f"Test CSV     : {TEST_CSV}",
             "=" * 72]
    for r in results:
        marker = " ← BEST" if r["key"] == best["key"] else ""
        lines += ["", "─" * 72, f"Model        : {r['name']}{marker}",
                  f"Test Accuracy: {r['accuracy']:.4f}  ({r['accuracy']*100:.2f}%)",
                  f"Test Macro-F1: {r['macro_f1']:.4f}", "",
                  "Per-intent classification report (test set):", r["report"]]
        if r["cm_path"]:
            lines.append(f"Confusion matrix saved: {r['cm_path']}")

    lines += ["", "=" * 72,
              f"BEST MODEL ON TEST SET : {best['name']}",
              f"  Test Accuracy        : {best['accuracy']:.4f}  ({best['accuracy']*100:.2f}%)",
              f"  Test Macro-F1        : {best['macro_f1']:.4f}", "=" * 72]

    # Blueprint target check note
    mlp_acc = next((r["accuracy"] for r in results if r["key"] == "mlp"), "N/A")
    mlp_f1  = next((r["macro_f1"]  for r in results if r["key"] == "mlp"), "N/A")
    lines += ["", "Blueprint target (>= 0.85 acc AND >= 0.85 macro-F1):",
              f"  MLP Accuracy : {mlp_acc}", f"  MLP Macro-F1 : {mlp_f1}", "=" * 72]

    report_text = "\n".join(lines)
    with open(os.path.join(eval_run_dir, "evaluation_report.txt"),
              "w", encoding="utf-8") as f:
        f.write(report_text)
    return report_text


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate a training run on the held-out test set.")
    parser.add_argument("--run", required=True,
                        help="Training run ID, e.g. train_001")
    args      = parser.parse_args()
    run_id    = args.run
    run_dir   = os.path.join(TRAINING_DIR, run_id)
    eval_id   = next_eval_id()
    eval_dir  = os.path.join(EVAL_DIR, eval_id)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("=" * 72)
    print(f"  EVALUATION RUN : {eval_id}")
    print(f"  Training run   : {run_id}")
    print(f"  Timestamp      : {timestamp}")
    print("=" * 72)

    if not os.path.isdir(run_dir):
        print(f"\nERROR: Training run not found: {run_dir}")
        if os.path.isdir(TRAINING_DIR):
            print("Available runs:")
            for d in sorted(os.listdir(TRAINING_DIR)):
                print(f"  {d}")
        return

    print(f"\nLoading test data from: {TEST_CSV}")
    X_test, y_test = load_test()
    print(f"  Test rows  : {len(X_test)}")
    print(f"  Label dist : {dict(sorted(Counter(y_test).items()))}")

    meta_path = os.path.join(run_dir, "metadata.json")
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            train_meta = json.load(f)
        print(f"\nTraining metadata loaded from: {meta_path}")
        print(f"  Models in run: {list(train_meta.get('models', {}).keys())}")

    os.makedirs(eval_dir, exist_ok=True)
    results = []
    print("\nEvaluating models ...")
    for model_file, display_name in MODEL_FILES.items():
        model_path = os.path.join(run_dir, model_file)
        if not os.path.exists(model_path):
            print(f"  Skipping {model_file} (not found)")
            continue
        print(f"\n  Loading: {model_path}")
        pipeline = joblib.load(model_path)
        results.append(evaluate_model(
            model_file, display_name, pipeline, X_test, y_test, eval_dir))

    if not results:
        print("\nNo models found to evaluate.")
        return

    print("\n" + "-" * 72)
    print("Test Set Summary:")
    print(f"  {'Model':<35} {'Accuracy':>10} {'Macro-F1':>10}")
    print("  " + "─" * 55)
    best = max(results, key=lambda r: r["macro_f1"])
    for r in results:
        marker = " ← BEST" if r["key"] == best["key"] else ""
        print(f"  {r['name']:<35} {r['accuracy']:>10.4f} {r['macro_f1']:>10.4f}{marker}")

    print(f"\nSaving evaluation artifacts to: {eval_dir}")
    save_eval_artifacts(eval_dir, eval_id, run_id, results, timestamp)

    print("\n" + "=" * 72)
    print(f"  Evaluation complete : {eval_id}")
    print(f"  Artifacts           : {eval_dir}")
    print(f"  Best model          : {best['name']}")
    print(f"  Test Accuracy       : {best['accuracy']:.4f}  ({best['accuracy']*100:.2f}%)")
    print(f"  Test Macro-F1       : {best['macro_f1']:.4f}")
    print("=" * 72)

    # Print blueprint target pass/fail
    mlp = next((r for r in results if r["key"] == "mlp"), None)
    if mlp:
        print(f"\nBlueprint target (>= 0.85 acc AND >= 0.85 macro-F1):")
        print(f"  MLP Accuracy : {mlp['accuracy']:.4f}  "
              f"{'✓ PASS' if mlp['accuracy'] >= 0.85 else '✗ BELOW TARGET'}")
        print(f"  MLP Macro-F1 : {mlp['macro_f1']:.4f}  "
              f"{'✓ PASS' if mlp['macro_f1'] >= 0.85 else '✗ BELOW TARGET'}")


if __name__ == "__main__":
    main()
