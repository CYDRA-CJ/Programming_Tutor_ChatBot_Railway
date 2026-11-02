# audit_dataset.py — validates data/intent_dataset.csv against current schema.
# Run from project root: .\.venv\Scripts\python.exe scripts\audit_dataset.py

import csv, io, json, os, sys
from collections import Counter, defaultdict

SRC         = os.path.join("data", "intent_dataset.csv")
REPORT_DIR  = "results"
REPORT_PATH = os.path.join(REPORT_DIR, "dataset_audit_report.txt")

# Current 7-column schema (review_status removed)
FIELDNAMES = [
    "text", "intents", "primary_intent", "topic_tags",
    "language_tags", "source_group", "context_required",
]

# Current 11 approved intents (debug_code + predict_output removed)
APPROVED_INTENTS = {
    "greeting", "bot_capabilities", "explain_concept", "show_syntax",
    "show_example", "generate_code", "explain_code",
    "compare_concepts", "request_quiz", "follow_up", "clarification",
}

APPROVED_LANGUAGES = {"python", "java", "c", "multiple", "unspecified"}
MINIMUM_PER_INTENT = 150


def parse_json_field(value):
    # Returns (parsed_list, error_message)
    try:
        result = json.loads(value)
        return (result, None) if isinstance(result, list) else (None, "not a JSON array")
    except json.JSONDecodeError as e:
        return None, str(e)


def jaccard(a, b):
    # Word-overlap similarity between two token sets
    if not a and not b:
        return 1.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def tokenize(text):
    return set(text.lower().split())


def audit():
    lines_out = []

    def log(msg=""):
        lines_out.append(msg)
        print(msg)

    log("=" * 70)
    log("DATASET AUDIT REPORT")
    log(f"File : {SRC}")
    log("=" * 70)

    # -- Check 1: file exists and parses --
    if not os.path.exists(SRC):
        log(f"[FAIL] File not found: {SRC}")
        return lines_out

    with open(SRC, "r", encoding="utf-8") as f:
        raw = f.read()

    rows = []
    parse_errors = 0
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith('"text"') or line.startswith("text,"):
            continue
        try:
            parsed = next(csv.reader(io.StringIO(line)))
        except StopIteration:
            parse_errors += 1
            continue
        if len(parsed) >= 7:
            rows.append(dict(zip(FIELDNAMES, parsed[:7])))
        else:
            parse_errors += 1

    log(f"\n[CHECK 1] CSV parsing")
    log(f"  Total rows parsed : {len(rows)}")
    log(f"  Parse errors      : {parse_errors}")
    log(f"  Result: {'PASS' if parse_errors == 0 else 'FAIL'}")

    # -- Check 2: 7-column schema --
    log(f"\n[CHECK 2] Schema — expected 7 columns")
    col_issues = sum(1 for r in rows if len(r) != 7)
    log(f"  Rows with wrong column count : {col_issues}")
    log(f"  Result: {'PASS' if col_issues == 0 else 'FAIL'}")

    # -- Check 3: no empty text fields --
    empty_text = [i for i, r in enumerate(rows) if not r.get("text", "").strip()]
    log(f"\n[CHECK 3] Non-empty text field")
    log(f"  Rows with empty text : {len(empty_text)}")
    log(f"  Result: {'PASS' if not empty_text else 'FAIL'}")

    # -- Check 4: JSON array fields parse correctly --
    log(f"\n[CHECK 4] JSON-array fields (intents, topic_tags, language_tags)")
    json_errors = []
    for i, r in enumerate(rows):
        for field in ("intents", "topic_tags", "language_tags"):
            _, err = parse_json_field(r.get(field, ""))
            if err:
                json_errors.append((i, field, err))
    log(f"  JSON parse errors : {len(json_errors)}")
    for i, field, err in json_errors[:10]:
        log(f"    Row {i+1}, '{field}': {err}  text='{rows[i]['text'][:60]}'")
    log(f"  Result: {'PASS' if not json_errors else 'FAIL'}")

    # -- Check 5: all intent labels are from the approved 11 --
    log(f"\n[CHECK 5] Approved intent labels (11 intents)")
    bad_intents = []
    for i, r in enumerate(rows):
        intents, err = parse_json_field(r.get("intents", "[]"))
        if err:
            continue
        for intent in intents:
            if intent not in APPROVED_INTENTS:
                bad_intents.append((i, intent, r["text"][:60]))
    log(f"  Rows with unapproved intent labels : {len(bad_intents)}")
    for item in bad_intents[:10]:
        log(f"    Row {item[0]+1}: '{item[1]}' — {item[2]}")
    log(f"  Result: {'PASS' if not bad_intents else 'FAIL'}")

    # -- Check 6: primary_intent appears inside intents list --
    log(f"\n[CHECK 6] primary_intent inside intents list")
    primary_mismatch = []
    for i, r in enumerate(rows):
        primary = r.get("primary_intent", "").strip().strip('"')
        intents, err = parse_json_field(r.get("intents", "[]"))
        if err or not intents:
            continue
        if primary not in intents:
            primary_mismatch.append((i, primary, intents, r["text"][:60]))
    log(f"  Mismatches : {len(primary_mismatch)}")
    for item in primary_mismatch[:10]:
        log(f"    Row {item[0]+1}: primary='{item[1]}' not in {item[2]}")
    log(f"  Result: {'PASS' if not primary_mismatch else 'FAIL'}")

    # -- Check 7: context_required is true or false --
    log(f"\n[CHECK 7] context_required is 'true' or 'false'")
    bad_ctx = [(i, r["context_required"]) for i, r in enumerate(rows)
               if r.get("context_required", "").lower() not in ("true", "false")]
    log(f"  Invalid values : {len(bad_ctx)}")
    for item in bad_ctx[:5]:
        log(f"    Row {item[0]+1}: '{item[1]}'")
    log(f"  Result: {'PASS' if not bad_ctx else 'FAIL'}")

    # -- Check 8: language_tags are approved values --
    log(f"\n[CHECK 8] Approved language_tag values")
    bad_langs = []
    for i, r in enumerate(rows):
        langs, err = parse_json_field(r.get("language_tags", "[]"))
        if err:
            continue
        for lang in langs:
            if lang not in APPROVED_LANGUAGES:
                bad_langs.append((i, lang, r["text"][:60]))
    log(f"  Rows with unapproved language tags : {len(bad_langs)}")
    for item in bad_langs[:10]:
        log(f"    Row {item[0]+1}: '{item[1]}' — {item[2]}")
    log(f"  Result: {'PASS' if not bad_langs else 'FAIL'}")

    # -- Check 9: per-intent row counts, minimum 150 each --
    log(f"\n[CHECK 9] Per-intent row counts (minimum = {MINIMUM_PER_INTENT})")
    intent_counts = Counter(
        r["primary_intent"].strip().strip('"') for r in rows
        if r.get("primary_intent", "").strip().strip('"') in APPROVED_INTENTS
    )
    below_min = []
    for intent in sorted(APPROVED_INTENTS):
        count = intent_counts.get(intent, 0)
        status = "OK" if count >= MINIMUM_PER_INTENT else "BELOW MIN"
        log(f"  {intent:<22} : {count:>4}  [{status}]")
        if count < MINIMUM_PER_INTENT:
            below_min.append((intent, count))
    log(f"  Total rows       : {sum(intent_counts.values())}")
    log(f"  Below minimum    : {len(below_min)}")
    log(f"  Result: {'PASS' if not below_min else 'WARN — some intents below minimum'}")

    # -- Check 10: per-language counts --
    log(f"\n[CHECK 10] Per-language row counts")
    lang_counts = Counter()
    context_only = 0
    for r in rows:
        langs, err = parse_json_field(r.get("language_tags", "[]"))
        if err:
            continue
        if not langs:
            context_only += 1
        for lang in langs:
            lang_counts[lang] += 1
    for lang in ["python", "java", "c"]:
        log(f"  {lang:<10} : {lang_counts.get(lang, 0):>4}")
    log(f"  context-only (no language tag) : {context_only}")
    log("  Result: INFO")

    # -- Check 11: multi-intent rows --
    log(f"\n[CHECK 11] Multi-intent rows")
    multi_rows = []
    for i, r in enumerate(rows):
        intents, err = parse_json_field(r.get("intents", "[]"))
        if err:
            continue
        if len(intents) > 1:
            multi_rows.append((i, intents))
    log(f"  Multi-intent rows  : {len(multi_rows)}")
    log(f"  Single-intent rows : {len(rows) - len(multi_rows)}")
    log(f"  Multi-intent %     : {100*len(multi_rows)/max(len(rows),1):.1f}%")
    log("  Result: INFO")

    # -- Check 12: exact duplicate text detection --
    log(f"\n[CHECK 12] Exact duplicate text detection")
    text_counts = Counter(r["text"].strip() for r in rows)
    exact_dupes = [(t, c) for t, c in text_counts.items() if c > 1]
    log(f"  Exact duplicate texts : {len(exact_dupes)}")
    for text, count in sorted(exact_dupes, key=lambda x: -x[1])[:10]:
        log(f"    ({count}x) '{text[:80]}'")
    log(f"  Result: {'PASS' if not exact_dupes else 'WARN — duplicates found'}")

    # -- Check 13: near-duplicate detection (Jaccard >= 0.85) — skipped for large datasets --
    log(f"\n[CHECK 13] Near-duplicate detection (Jaccard >= 0.85)")
    if len(rows) > 3000:
        log(f"  Skipped — dataset has {len(rows)} rows (O(n²) too slow above 3000)")
        log("  Result: SKIPPED")
    else:
        texts      = [r["text"].strip() for r in rows]
        token_sets = [tokenize(t) for t in texts]
        near_pairs = []
        for i in range(len(token_sets)):
            for j in range(i + 1, len(token_sets)):
                if jaccard(token_sets[i], token_sets[j]) >= 0.85:
                    near_pairs.append((i, j))
        log(f"  Near-duplicate pairs : {len(near_pairs)}")
        for i, j in near_pairs[:5]:
            log(f"    Row {i+1}: '{texts[i][:60]}'")
            log(f"    Row {j+1}: '{texts[j][:60]}'")
        log(f"  Result: {'PASS' if not near_pairs else 'WARN — review near-duplicates'}")

    # -- Check 14: language-topic consistency --
    log(f"\n[CHECK 14] Language-topic tag consistency")
    warns = []
    for i, r in enumerate(rows):
        topics, _ = parse_json_field(r.get("topic_tags", "[]"))
        langs, _  = parse_json_field(r.get("language_tags", "[]"))
        if not topics or not langs:
            continue
        for topic in topics:
            if topic.startswith("java_") and "java" not in langs:
                warns.append((i, "java", topic))
            if topic.startswith("c_") and "c" not in langs:
                warns.append((i, "c", topic))
            if topic.startswith("python_") and "python" not in langs:
                warns.append((i, "python", topic))
    log(f"  Consistency warnings : {len(warns)}")
    for i, lang, topic in warns[:10]:
        log(f"    Row {i+1}: topic '{topic}' but '{lang}' not in language_tags")
    log(f"  Result: {'PASS' if not warns else 'WARN'}")

    # -- Final summary --
    log(f"\n{'='*70}")
    log("SUMMARY")
    log(f"{'='*70}")
    log(f"  Total rows              : {len(rows)}")
    log(f"  Parse errors            : {parse_errors}")
    log(f"  Schema issues           : {col_issues}")
    log(f"  Empty text              : {len(empty_text)}")
    log(f"  JSON field errors       : {len(json_errors)}")
    log(f"  Unapproved intents      : {len(bad_intents)}")
    log(f"  primary_intent mismatches: {len(primary_mismatch)}")
    log(f"  Bad context_required    : {len(bad_ctx)}")
    log(f"  Unapproved language tags: {len(bad_langs)}")
    log(f"  Exact duplicates        : {len(exact_dupes)}")

    hard_failures = (
        parse_errors + col_issues + len(empty_text) + len(json_errors)
        + len(bad_intents) + len(primary_mismatch)
        + len(bad_ctx) + len(bad_langs)
    )

    if hard_failures == 0 and not below_min:
        log("\n  OVERALL VERDICT: PASS")
    elif hard_failures == 0 and below_min:
        log("\n  OVERALL VERDICT: PASS WITH WARNINGS")
    else:
        log(f"\n  OVERALL VERDICT: FAIL — {hard_failures} hard failure(s)")

    log(f"\nReport saved to: {REPORT_PATH}")
    log("=" * 70)
    return lines_out


def main():
    os.makedirs(REPORT_DIR, exist_ok=True)
    lines = audit()
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
