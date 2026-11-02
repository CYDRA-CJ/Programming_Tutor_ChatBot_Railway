# split_dataset.py — splits intent_dataset.csv into train/val/test (70/15/15).
# Stratified by intent, group-aware (same source_group stays in one split).
# Always overwrites data/splits/ — run this before retraining after adding new rows.
# Run from project root: .\.venv\Scripts\python.exe scripts\split_dataset.py

import csv, io, json, os, random
from collections import Counter, defaultdict
from datetime import datetime

SRC        = os.path.join("data", "intent_dataset.csv")
OUT_DIR    = os.path.join("data", "splits")
TRAIN_PATH = os.path.join(OUT_DIR, "train.csv")
VAL_PATH   = os.path.join(OUT_DIR, "val.csv")
TEST_PATH  = os.path.join(OUT_DIR, "test.csv")
REPORT     = os.path.join(OUT_DIR, "split_report.txt")

# Current 7-column schema (review_status removed)
FIELDNAMES = [
    "text", "intents", "primary_intent", "topic_tags",
    "language_tags", "source_group", "context_required",
]

# Current 11 approved intents
APPROVED_INTENTS = {
    "greeting", "bot_capabilities", "explain_concept", "show_syntax",
    "show_example", "generate_code", "explain_code",
    "compare_concepts", "request_quiz", "follow_up", "clarification",
}

RANDOM_SEED = 42
TRAIN_RATIO = 0.70
VAL_RATIO   = 0.15
# TEST_RATIO  = 0.15 (remainder)


def load_rows():
    # Load and filter rows — only keep rows with approved intents
    with open(SRC, "r", encoding="utf-8") as f:
        raw = f.read()
    rows = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith('"text"') or line.startswith("text,"):
            continue
        try:
            parsed = next(csv.reader(io.StringIO(line)))
        except StopIteration:
            continue
        if len(parsed) >= 7:
            row    = dict(zip(FIELDNAMES, parsed[:7]))
            intent = row["primary_intent"].strip().strip('"')
            if intent in APPROVED_INTENTS:
                rows.append(row)
    return rows


def build_groups(rows):
    # Group rows by (intent, source_group) so paraphrases stay in the same split
    rng = random.Random(RANDOM_SEED)
    by_intent_group = defaultdict(lambda: defaultdict(list))
    for row in rows:
        intent = row["primary_intent"].strip().strip('"')
        group  = row.get("source_group", "").strip() or "__no_group__"
        by_intent_group[intent][group].append(row)

    # Shuffle groups within each intent for random but reproducible splits
    intent_groups = {}
    for intent, groups in by_intent_group.items():
        group_list = list(groups.values())
        rng.shuffle(group_list)
        intent_groups[intent] = group_list
    return intent_groups


def split_intent(groups, train_r, val_r):
    # Assign groups to train/val/test based on target row counts
    total        = sum(len(g) for g in groups)
    target_train = round(total * train_r)
    target_val   = round(total * val_r)
    train_rows, val_rows, test_rows = [], [], []
    n_train = n_val = 0
    for group in groups:
        if n_train < target_train:
            train_rows.extend(group); n_train += len(group)
        elif n_val < target_val:
            val_rows.extend(group);   n_val   += len(group)
        else:
            test_rows.extend(group)
    return train_rows, val_rows, test_rows


def split_all(intent_groups):
    rng = random.Random(RANDOM_SEED)
    all_train, all_val, all_test = [], [], []
    for intent, groups in sorted(intent_groups.items()):
        tr, va, te = split_intent(groups, TRAIN_RATIO, VAL_RATIO)
        all_train.extend(tr); all_val.extend(va); all_test.extend(te)
    # Shuffle so intents are interleaved during training
    rng.shuffle(all_train); rng.shuffle(all_val); rng.shuffle(all_test)
    return all_train, all_val, all_test


def write_csv(rows, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)


def balance_report(train, val, test, total):
    lines = []
    lines.append("=" * 72)
    lines.append("SPLIT REPORT")
    lines.append(f"Generated : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Source    : {SRC}")
    lines.append(f"Seed      : {RANDOM_SEED}")
    lines.append("=" * 72)
    lines.append(f"\nTotal rows : {total}")
    lines.append(f"Train      : {len(train):>5}  ({100*len(train)/total:.1f}%)")
    lines.append(f"Validation : {len(val):>5}  ({100*len(val)/total:.1f}%)")
    lines.append(f"Test       : {len(test):>5}  ({100*len(test)/total:.1f}%)")

    lines.append(f"\n{'Intent':<24} {'Train':>7} {'Val':>7} {'Test':>7} {'Total':>7}")
    lines.append("-" * 52)

    tr_c  = Counter(r["primary_intent"].strip().strip('"') for r in train)
    val_c = Counter(r["primary_intent"].strip().strip('"') for r in val)
    te_c  = Counter(r["primary_intent"].strip().strip('"') for r in test)

    for intent in sorted(set(tr_c) | set(val_c) | set(te_c)):
        tr = tr_c.get(intent, 0); va = val_c.get(intent, 0); te = te_c.get(intent, 0)
        lines.append(f"{intent:<24} {tr:>7} {va:>7} {te:>7} {tr+va+te:>7}")

    lines.append("-" * 52)
    lines.append(f"{'TOTAL':<24} {len(train):>7} {len(val):>7} {len(test):>7} "
                 f"{len(train)+len(val)+len(test):>7}")

    # Language distribution in train split (language-specific intents only)
    lines.append(f"\n{'─'*72}")
    lines.append("Language distribution in TRAIN split:")
    lines.append(f"{'Intent':<24} {'Python':>8} {'Java':>8} {'C':>8} {'Unspec':>8}")
    lines.append("-" * 52)

    # Only intents that have language-specific rows
    SPECIFIC = [
        "explain_concept", "show_syntax", "show_example", "generate_code",
        "explain_code", "compare_concepts", "request_quiz",
    ]
    for intent in SPECIFIC:
        intent_rows = [r for r in train
                       if r["primary_intent"].strip().strip('"') == intent]
        py = ja = c = un = 0
        for row in intent_rows:
            try:
                langs = json.loads(row["language_tags"])
            except Exception:
                langs = []
            if not langs:
                un += 1
            else:
                for lang in langs:
                    if lang == "python": py += 1
                    elif lang == "java": ja += 1
                    elif lang == "c":    c  += 1
        lines.append(f"{intent:<24} {py:>8} {ja:>8} {c:>8} {un:>8}")

    lines.append("=" * 72)
    return "\n".join(lines)


def main():
    print(f"Loading {SRC} ...")
    rows = load_rows()
    print(f"  {len(rows)} valid rows loaded.")

    print("Building source groups ...")
    intent_groups = build_groups(rows)
    for intent, groups in sorted(intent_groups.items()):
        row_count = sum(len(g) for g in groups)
        print(f"  {intent:<24}: {len(groups):>4} groups, {row_count:>4} rows")

    print("\nSplitting (70 / 15 / 15) ...")
    train, val, test = split_all(intent_groups)
    total = len(train) + len(val) + len(test)
    print(f"  Train : {len(train):>5} rows  ({100*len(train)/total:.1f}%)")
    print(f"  Val   : {len(val):>5}  rows  ({100*len(val)/total:.1f}%)")
    print(f"  Test  : {len(test):>5}  rows  ({100*len(test)/total:.1f}%)")

    print("\nWriting split files ...")
    write_csv(train, TRAIN_PATH); write_csv(val, VAL_PATH); write_csv(test, TEST_PATH)
    print(f"  {TRAIN_PATH}\n  {VAL_PATH}\n  {TEST_PATH}")

    report = balance_report(train, val, test, total)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nBalance report saved to: {REPORT}")
    print("\n" + report)


if __name__ == "__main__":
    main()
