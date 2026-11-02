# count_kb.py — shows a summary count of all 4 knowledge base JSON files.
#
# Files counted:
#   data/knowledge_base.json   — KB records by language and topic
#   data/code_examples.json    — examples by language
#   data/code_templates.json   — templates by language, with/without parameters
#   data/quizzes.json          — quizzes by language and question type
#
# Run from project root: .\.venv\Scripts\python.exe scripts\count_kb.py

import json, os
from collections import Counter

DATA_DIR = "data"


def load_json(filename):
    # Load a JSON file — return None if it fails
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        print(f"  ERROR: File not found: {path}")
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def count_knowledge_base():
    section("KNOWLEDGE BASE  (knowledge_base.json)")
    data = load_json("knowledge_base.json")
    if not data:
        return
    records = data.get("records", [])
    print(f"  Total records : {len(records)}")
    print()

    # Count by language
    by_lang = Counter(r.get("language", "?") for r in records)
    print("  By language:")
    for lang in ["python", "java", "c", "shared"]:
        print(f"    {lang:10s}: {by_lang.get(lang, 0):4d}")
    print()

    # Count by level
    by_level = Counter(r.get("level", "?") for r in records)
    print("  By level:")
    for level, cnt in sorted(by_level.items()):
        print(f"    {level:15s}: {cnt:4d}")
    print()

    # Count unique topics
    topics = set(r.get("topic", "") for r in records)
    print(f"  Distinct topics: {len(topics)}")
    print()

    # Count total keywords and aliases
    total_kw = sum(len(r.get("keywords", [])) for r in records)
    total_al = sum(len(r.get("aliases",  [])) for r in records)
    print(f"  Total keywords : {total_kw}")
    print(f"  Total aliases  : {total_al}")
    print(f"  Combined       : {total_kw + total_al}")


def count_code_examples():
    section("CODE EXAMPLES  (code_examples.json)")
    data = load_json("code_examples.json")
    if not data:
        return
    examples = data.get("examples", [])
    print(f"  Total examples : {len(examples)}")
    print()

    # Count by language
    by_lang = Counter(e.get("language", "?") for e in examples)
    print("  By language:")
    for lang in ["python", "java", "c"]:
        print(f"    {lang:10s}: {by_lang.get(lang, 0):4d}")
    print()

    # Count unique topics
    topics = set(e.get("topic", "") for e in examples)
    print(f"  Distinct topics: {len(topics)}")

    # Check which examples have output field
    with_output = sum(1 for e in examples if e.get("output", "").strip())
    print(f"  With output    : {with_output}")


def count_code_templates():
    section("CODE TEMPLATES  (code_templates.json)")
    data = load_json("code_templates.json")
    if not data:
        return
    templates = data.get("templates", [])
    print(f"  Total templates : {len(templates)}")
    print()

    # Count by language
    by_lang = Counter(t.get("language", "?") for t in templates)
    print("  By language:")
    for lang in ["python", "java", "c"]:
        print(f"    {lang:10s}: {by_lang.get(lang, 0):4d}")
    print()

    # Count parameterised vs static
    with_params    = sum(1 for t in templates if t.get("parameters"))
    without_params = len(templates) - with_params
    print(f"  With parameters (user values substituted): {with_params}")
    print(f"  Static (default values only)             : {without_params}")
    print()

    # List templates that have parameters — first 10
    print("  Sample parameterised templates:")
    count = 0
    for t in templates:
        if t.get("parameters") and count < 10:
            param_names = [p["name"] for p in t["parameters"]]
            print(f"    {t['id']:40s} params={param_names}")
            count += 1
    if with_params > 10:
        print(f"    ... and {with_params - 10} more")


def count_quizzes():
    section("QUIZZES  (quizzes.json)")
    data = load_json("quizzes.json")
    if not data:
        return
    quizzes = data.get("quizzes", [])
    print(f"  Total questions : {len(quizzes)}")
    print()

    # Count by question type
    by_type = Counter(q.get("question_type", "?") for q in quizzes)
    print("  By question type:")
    for qtype, cnt in sorted(by_type.items()):
        print(f"    {qtype:30s}: {cnt:4d}")
    print()

    # Count by language
    by_lang = Counter(q.get("language", "?") for q in quizzes)
    print("  By language:")
    for lang in ["python", "java", "c"]:
        print(f"    {lang:10s}: {by_lang.get(lang, 0):4d}")
    print()

    # Count unique topics
    topics = set(q.get("topic", "") for q in quizzes)
    print(f"  Distinct topics: {len(topics)}")
    print()

    # Per topic per language for MC questions only
    mc = [q for q in quizzes if q.get("question_type") == "multiple_choice"]
    print(f"  MC questions per topic per language (min/max):")
    from collections import defaultdict
    topic_lang_counts = defaultdict(lambda: Counter())
    for q in mc:
        topic_lang_counts[q.get("topic", "?")][q.get("language", "?")] += 1
    per_topic_totals = {
        topic: sum(counts.values())
        for topic, counts in topic_lang_counts.items()
    }
    min_topic = min(per_topic_totals, key=per_topic_totals.get) if per_topic_totals else "?"
    max_topic = max(per_topic_totals, key=per_topic_totals.get) if per_topic_totals else "?"
    min_val   = per_topic_totals.get(min_topic, 0)
    max_val   = per_topic_totals.get(max_topic, 0)
    print(f"    Min: {min_val} questions  ({min_topic})")
    print(f"    Max: {max_val} questions  ({max_topic})")


def grand_total():
    section("GRAND TOTAL")
    totals = [
        ("knowledge_base.json",  "records",   "KB records"),
        ("code_examples.json",   "examples",  "Code examples"),
        ("code_templates.json",  "templates", "Code templates"),
        ("quizzes.json",         "quizzes",   "Quiz questions"),
    ]
    overall = 0
    for fname, key, label in totals:
        data = load_json(fname)
        if data:
            count = len(data.get(key, []))
            print(f"  {label:20s}: {count:5d}")
            overall += count
    print(f"  {'TOTAL':20s}: {overall:5d}")
    print(f"{'='*60}")


def main():
    print("=" * 60)
    print("KNOWLEDGE BASE COUNT SUMMARY")
    print("=" * 60)

    count_knowledge_base()
    count_code_examples()
    count_code_templates()
    count_quizzes()
    grand_total()


if __name__ == "__main__":
    main()
