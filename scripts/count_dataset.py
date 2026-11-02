# count_dataset.py — summary table of dataset counts by intent and language.
# Run from project root: .\.venv\Scripts\python.exe scripts\count_dataset.py

import csv, io, json, os
from collections import Counter, defaultdict

SRC = os.path.join("data", "intent_dataset.csv")

# Current 7-column schema (review_status removed)
FIELDNAMES = [
    "text", "intents", "primary_intent", "topic_tags",
    "language_tags", "source_group", "context_required",
]

# Language-independent intents (shown as "global" — no per-language breakdown)
GLOBAL_INTENTS = ["greeting", "bot_capabilities", "follow_up", "clarification"]

# Language-specific intents (shown with Python / Java / C columns)
SPECIFIC_INTENTS = [
    "explain_concept", "show_syntax", "show_example", "generate_code",
    "explain_code", "compare_concepts", "request_quiz",
]

ALL_INTENTS = SPECIFIC_INTENTS + GLOBAL_INTENTS


def load_rows():
    if not os.path.exists(SRC):
        print(f"ERROR: {SRC} not found.")
        return []
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
            rows.append(dict(zip(FIELDNAMES, parsed[:7])))
    return rows


def count_dataset(rows):
    # breakdown[intent][language] = count
    breakdown = defaultdict(lambda: Counter())
    total_per_intent = Counter()

    for row in rows:
        intent = row["primary_intent"].strip().strip('"')
        if intent not in ALL_INTENTS:
            continue
        total_per_intent[intent] += 1
        try:
            langs = json.loads(row["language_tags"])
        except Exception:
            langs = []

        if not langs:
            breakdown[intent]["unspecified"] += 1
        else:
            seen = set()
            for lang in langs:
                if lang in ("python", "java", "c") and lang not in seen:
                    breakdown[intent][lang] += 1
                    seen.add(lang)

    return breakdown, total_per_intent


def print_table(breakdown, total_per_intent, grand_total):
    W_INTENT = 22
    W_NUM    = 7

    sep = f"{'─'*W_INTENT}─{'─'*W_NUM}─{'─'*W_NUM}─{'─'*W_NUM}─{'─'*W_NUM}─{'─'*W_NUM}"

    def row_line(intent, total, py, ja, c, un):
        return (f"{intent:<{W_INTENT}} {total:>{W_NUM}} "
                f"{py:>{W_NUM}} {ja:>{W_NUM}} {c:>{W_NUM}} {un:>{W_NUM}}")

    print()
    print("=" * 70)
    print("  DATASET COUNT SUMMARY")
    print(f"  File: {SRC}")
    print("=" * 70)
    print()
    print(row_line("Intent", "Total", "Python", "Java", "C", "Unspec"))
    print(sep)

    # Language-specific intents
    total_py = total_ja = total_c = total_un = 0
    for intent in SPECIFIC_INTENTS:
        d   = breakdown[intent]
        tot = total_per_intent.get(intent, 0)
        py  = d.get("python", 0)
        ja  = d.get("java", 0)
        c   = d.get("c", 0)
        un  = d.get("unspecified", 0)
        total_py += py; total_ja += ja; total_c += c; total_un += un
        print(row_line(intent, tot, py, ja, c, un))

    print(sep)

    # Global intents — no language breakdown
    global_total = 0
    for intent in GLOBAL_INTENTS:
        tot = total_per_intent.get(intent, 0)
        global_total += tot
        print(row_line(intent, tot, "—", "—", "—", "global"))

    print(sep)

    # Grand total
    print(row_line("TOTAL", f"{grand_total:,}",
                   f"{total_py:,}", f"{total_ja:,}", f"{total_c:,}",
                   f"{total_un + global_total:,}"))
    print()

    # Minimum check — all language-specific intents should have ≥150 per language
    print("  Minimum per language per specific intent: 150")
    all_ok = True
    for intent in SPECIFIC_INTENTS:
        d = breakdown[intent]
        issues = []
        for lang, label in [("python","Python"),("java","Java"),("c","C")]:
            if d.get(lang, 0) < 150:
                issues.append(f"{label}={d.get(lang,0)}")
        if issues:
            print(f"  WARN  {intent:<22}: BELOW MIN — {', '.join(issues)}")
            all_ok = False
    if all_ok:
        print("  PASS  All language-specific intents meet the 150-row minimum.")
    print()

    # Minimum check — global intents should have ≥150 total
    print("  Minimum per global intent: 150")
    all_global_ok = True
    for intent in GLOBAL_INTENTS:
        tot = total_per_intent.get(intent, 0)
        if tot < 150:
            print(f"  WARN  {intent:<22}: BELOW MIN — total={tot}")
            all_global_ok = False
    if all_global_ok:
        print("  PASS  All global intents meet the 150-row minimum.")
    print()
    print("=" * 70)


def print_language_bars(breakdown):
    # Visual bar chart — each block ≈ 10 rows
    print()
    print("  Language distribution per specific intent  (each █ ≈ 10 rows)")
    print()
    for intent in SPECIFIC_INTENTS:
        d  = breakdown[intent]
        py = d.get("python", 0)
        ja = d.get("java", 0)
        c  = d.get("c", 0)
        un = d.get("unspecified", 0)
        print(f"  {intent:<22}")
        print(f"    Python  ({py:>4})  {'█' * (py // 10)}")
        print(f"    Java    ({ja:>4})  {'█' * (ja // 10)}")
        print(f"    C       ({c:>4})  {'█' * (c  // 10)}")
        if un:
            print(f"    Unspec  ({un:>4})  {'░' * (un // 10)}")
        print()
    print("=" * 70)


def main():
    rows = load_rows()
    if not rows:
        return
    breakdown, total_per_intent = count_dataset(rows)
    grand_total = len(rows)
    print_table(breakdown, total_per_intent, grand_total)
    print_language_bars(breakdown)
    print(f"  Total rows : {grand_total:,}")
    print(f"  File       : {os.path.abspath(SRC)}")
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()
