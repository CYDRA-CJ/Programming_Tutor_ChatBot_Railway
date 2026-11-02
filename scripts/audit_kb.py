# audit_kb.py — checks all 4 knowledge base JSON files for quality issues.
#
# Files checked:
#   data/knowledge_base.json   — 112 KB records
#   data/code_examples.json    — 220 code examples
#   data/code_templates.json   — 197 code templates
#   data/quizzes.json          — 533 quiz questions
#
# Checks performed for each file:
#   1. File loads without errors
#   2. Required fields are present on every record
#   3. No duplicate IDs
#   4. No empty required text fields
#   5. Language values are valid (python / java / c / shared)
#   6. Quiz-specific: correct_index is valid, options list not empty
#   7. Template-specific: template field not empty
#
# Duplicates are shown with their approximate line number in the JSON file.
#
# Run from project root: .\.venv\Scripts\python.exe scripts\audit_kb.py

import json, os
from collections import Counter

DATA_DIR = "data"

# Valid language values across all files
VALID_LANGUAGES = {"python", "java", "c", "shared"}

# Required fields per file type
REQUIRED_FIELDS = {
    "kb":        {"id", "language", "topic", "title", "level", "definition"},
    "examples":  {"id", "language", "topic", "title", "code"},
    "templates": {"id", "language", "topic", "title", "template"},
    "quizzes":   {"id", "language", "topic", "question_type", "question"},
}

# Valid quiz types
VALID_QUIZ_TYPES = {"multiple_choice", "fill_in_blank", "fill_in_blank_mc"}


def load_json(filename):
    # Load a JSON file — return None if it fails
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        print(f"  ERROR: File not found: {path}")
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def find_duplicate_line(filepath, duplicate_id):
    # Find the approximate line number of a duplicate ID in the JSON file.
    # Looks for: "id": "the_id" pattern
    with open(filepath, encoding="utf-8") as f:
        lines = f.readlines()
    matches = []
    search  = f'"id": "{duplicate_id}"'
    for i, line in enumerate(lines, 1):
        if search in line:
            matches.append(i)
    return matches


def audit_records(records, file_type, filename, filepath):
    # Run all checks on a list of records and print results
    required = REQUIRED_FIELDS[file_type]
    passed   = True

    # --- Check 1: required fields ---
    missing_fields = []
    for i, rec in enumerate(records):
        missing = required - set(rec.keys())
        if missing:
            missing_fields.append((i + 1, rec.get("id", "?"), missing))

    if missing_fields:
        passed = False
        print(f"  [FAIL] Missing required fields ({len(missing_fields)} records):")
        for pos, rid, fields in missing_fields[:5]:
            print(f"    Record #{pos} id='{rid}': missing {fields}")
        if len(missing_fields) > 5:
            print(f"    ... and {len(missing_fields) - 5} more")
    else:
        print(f"  [PASS] All records have required fields")

    # --- Check 2: duplicate IDs ---
    id_counts = Counter(rec.get("id", "") for rec in records)
    duplicates = {rid: count for rid, count in id_counts.items() if count > 1}

    if duplicates:
        passed = False
        print(f"  [FAIL] Duplicate IDs found ({len(duplicates)}):")
        for rid, count in list(duplicates.items())[:10]:
            line_nums = find_duplicate_line(filepath, rid)
            lines_str = ", ".join(f"line {n}" for n in line_nums)
            print(f"    id='{rid}' appears {count} times  ({lines_str})")
    else:
        print(f"  [PASS] No duplicate IDs")

    # --- Check 3: empty required text fields ---
    empty_text = []
    text_fields = {"title", "definition", "code", "template", "question"}
    for i, rec in enumerate(records):
        for field in text_fields & required:
            value = rec.get(field, "")
            if isinstance(value, str) and not value.strip():
                empty_text.append((i + 1, rec.get("id", "?"), field))

    if empty_text:
        passed = False
        print(f"  [FAIL] Empty text fields ({len(empty_text)}):")
        for pos, rid, field in empty_text[:5]:
            print(f"    Record #{pos} id='{rid}': field '{field}' is empty")
    else:
        print(f"  [PASS] No empty required text fields")

    # --- Check 4: valid language values ---
    bad_lang = []
    for i, rec in enumerate(records):
        lang = rec.get("language", "")
        if lang not in VALID_LANGUAGES:
            bad_lang.append((i + 1, rec.get("id", "?"), lang))

    if bad_lang:
        passed = False
        print(f"  [FAIL] Invalid language values ({len(bad_lang)}):")
        for pos, rid, lang in bad_lang[:5]:
            print(f"    Record #{pos} id='{rid}': language='{lang}'")
    else:
        print(f"  [PASS] All language values are valid")

    # --- Check 5 (quizzes only): valid question_type and correct_index ---
    if file_type == "quizzes":
        bad_type = []
        bad_idx  = []
        for i, rec in enumerate(records):
            qt = rec.get("question_type", "")
            if qt not in VALID_QUIZ_TYPES:
                bad_type.append((i + 1, rec.get("id", "?"), qt))
            # For multiple_choice: check correct_index is within options range
            if qt == "multiple_choice":
                options = rec.get("options", [])
                idx     = rec.get("correct_index", -1)
                if not isinstance(idx, int) or not (0 <= idx < len(options)):
                    bad_idx.append((i + 1, rec.get("id", "?"), idx, len(options)))

        if bad_type:
            passed = False
            print(f"  [FAIL] Invalid question_type ({len(bad_type)}):")
            for pos, rid, qt in bad_type[:5]:
                print(f"    Record #{pos} id='{rid}': question_type='{qt}'")
        else:
            print(f"  [PASS] All question types are valid")

        if bad_idx:
            passed = False
            print(f"  [FAIL] correct_index out of range ({len(bad_idx)}):")
            for pos, rid, idx, n_opts in bad_idx[:5]:
                print(f"    Record #{pos} id='{rid}': correct_index={idx} but {n_opts} options")
        else:
            print(f"  [PASS] All correct_index values are valid")

    return passed


def audit_file(filename, records_key):
    filepath = os.path.join(DATA_DIR, filename)
    print(f"\n{'='*60}")
    print(f"AUDITING: {filename}")
    print(f"{'='*60}")

    data = load_json(filename)
    if data is None:
        return False

    records = data.get(records_key, [])
    print(f"  Total records : {len(records)}")

    # Map filename to type key
    type_map = {
        "knowledge_base.json":  "kb",
        "code_examples.json":   "examples",
        "code_templates.json":  "templates",
        "quizzes.json":         "quizzes",
    }
    file_type = type_map.get(filename, "kb")

    passed = audit_records(records, file_type, filename, filepath)

    print()
    print(f"  VERDICT: {'PASS' if passed else 'FAIL'}")
    return passed


def main():
    print("=" * 60)
    print("KNOWLEDGE BASE AUDIT")
    print("=" * 60)

    # File name → key that holds the list of records
    files = [
        ("knowledge_base.json",  "records"),
        ("code_examples.json",   "examples"),
        ("code_templates.json",  "templates"),
        ("quizzes.json",         "quizzes"),
    ]

    results = []
    for filename, records_key in files:
        passed = audit_file(filename, records_key)
        results.append((filename, passed))

    # Summary
    print(f"\n{'='*60}")
    print("OVERALL SUMMARY")
    print(f"{'='*60}")
    all_passed = True
    for filename, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {status}  {filename}")
        if not passed:
            all_passed = False

    print()
    print(f"  OVERALL VERDICT: {'PASS' if all_passed else 'FAIL - see details above'}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
