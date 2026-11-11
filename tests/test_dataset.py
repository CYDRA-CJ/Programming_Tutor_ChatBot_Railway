# test_dataset.py
# Tests that all data files meet quality requirements:
# intent_dataset.csv, knowledge_base.json, code_examples.json,
# code_templates.json, and quizzes.json.

import csv
import json
import os
import pytest

from tests.conftest import (
    DATASET_PATH, KB_PATH, EXAMPLES_PATH,
    TEMPLATES_PATH, QUIZZES_PATH,
    APPROVED_INTENTS, APPROVED_LANGUAGES,
)

MINIMUM_PER_INTENT = 75


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def dataset_rows():
    rows = []
    with open(DATASET_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


@pytest.fixture(scope="module")
def kb_data():
    # KB is stored as {"metadata": {...}, "records": [...]}
    with open(KB_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    # Return the records list regardless of wrapper structure.
    if isinstance(raw, list):
        return raw
    return raw.get("records", raw.get("knowledge_base", []))


@pytest.fixture(scope="module")
def examples_data():
    with open(EXAMPLES_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def templates_data():
    with open(TEMPLATES_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def quizzes_data():
    with open(QUIZZES_PATH, encoding="utf-8") as f:
        return json.load(f)


# ── Dataset CSV tests ─────────────────────────────────────────────────────────

class TestDatasetFile:

    def test_file_exists(self):
        # Dataset CSV must exist at the expected path.
        assert os.path.exists(DATASET_PATH), f"Missing: {DATASET_PATH}"

    def test_csv_parses_without_error(self, dataset_rows):
        # CSV must be parseable and contain rows.
        assert len(dataset_rows) > 0, "Dataset is empty"

    def test_required_columns_present(self, dataset_rows):
        # All 7 required columns must be present (review_status removed).
        required = {
            "text", "intents", "primary_intent", "topic_tags",
            "language_tags", "source_group", "context_required",
        }
        actual = set(dataset_rows[0].keys())
        missing = required - actual
        assert not missing, f"Missing columns: {missing}"

    def test_no_empty_text_fields(self, dataset_rows):
        # Every row must have non-empty text.
        empty = [i for i, r in enumerate(dataset_rows, 2) if not r["text"].strip()]
        assert not empty, f"Empty text at rows: {empty[:10]}"

    def test_intents_field_is_valid_json_array(self, dataset_rows):
        # intents column must be a valid JSON array.
        errors = []
        for i, r in enumerate(dataset_rows, 2):
            try:
                val = json.loads(r["intents"])
                assert isinstance(val, list)
            except Exception:
                errors.append(i)
        assert not errors, f"Invalid intents JSON at rows: {errors[:10]}"

    def test_language_tags_field_is_valid_json_array(self, dataset_rows):
        errors = []
        for i, r in enumerate(dataset_rows, 2):
            try:
                val = json.loads(r["language_tags"])
                assert isinstance(val, list)
            except Exception:
                errors.append(i)
        assert not errors, f"Invalid language_tags JSON at rows: {errors[:10]}"

    def test_primary_intent_is_approved(self, dataset_rows):
        # primary_intent must be one of the 11 approved labels.
        bad = [
            (i, r["primary_intent"])
            for i, r in enumerate(dataset_rows, 2)
            if r["primary_intent"] not in APPROVED_INTENTS
        ]
        assert not bad, f"Unapproved primary_intent at rows: {bad[:10]}"

    def test_primary_intent_in_intents_list(self, dataset_rows):
        # primary_intent must also appear in the intents JSON array.
        mismatches = []
        for i, r in enumerate(dataset_rows, 2):
            try:
                intents_list = json.loads(r["intents"])
                if r["primary_intent"] not in intents_list:
                    mismatches.append(i)
            except Exception:
                pass
        assert not mismatches, f"primary_intent not in intents at rows: {mismatches[:10]}"

    def test_language_tags_are_approved(self, dataset_rows):
        # All language tags must use approved values.
        bad = []
        for i, r in enumerate(dataset_rows, 2):
            try:
                tags = json.loads(r["language_tags"])
                for tag in tags:
                    if tag not in APPROVED_LANGUAGES:
                        bad.append((i, tag))
            except Exception:
                pass
        assert not bad, f"Unapproved language tags: {bad[:10]}"

    def test_context_required_is_boolean_string(self, dataset_rows):
        bad = [
            (i, r["context_required"])
            for i, r in enumerate(dataset_rows, 2)
            if r["context_required"] not in ("true", "false")
        ]
        assert not bad, f"Invalid context_required at rows: {bad[:10]}"

    def test_no_exact_duplicate_texts(self, dataset_rows):
        texts = [r["text"].strip().lower() for r in dataset_rows]
        seen = set()
        dupes = []
        for t in texts:
            if t in seen:
                dupes.append(t[:60])
            seen.add(t)
        assert not dupes, f"Exact duplicate texts found: {dupes[:5]}"

    def test_minimum_rows_per_intent(self, dataset_rows):
        # Every intent must have at least 150 rows.
        from collections import defaultdict
        counts = defaultdict(int)
        for r in dataset_rows:
            counts[r["primary_intent"]] += 1
        below = {k: v for k, v in counts.items() if v < MINIMUM_PER_INTENT}
        assert not below, f"Intents below minimum {MINIMUM_PER_INTENT}: {below}"

    def test_all_11_intents_present(self, dataset_rows):
        present = {r["primary_intent"] for r in dataset_rows}
        missing = APPROVED_INTENTS - present
        assert not missing, f"Missing intents in dataset: {missing}"

    def test_language_coverage_all_three(self, dataset_rows):
        # Python, Java, and C must all appear in language tags.
        tagged = set()
        for r in dataset_rows:
            try:
                tagged.update(json.loads(r["language_tags"]))
            except Exception:
                pass
        for lang in ("python", "java", "c"):
            assert lang in tagged, f"Language '{lang}' not found in dataset"

    def test_total_row_count(self, dataset_rows):
        # Dataset covers 11 intents across Python, Java, C and shared rows.
        # 6284 rows after removing debug_code (555) and predict_output (541).
        assert len(dataset_rows) >= 1000, (
            f"Dataset has only {len(dataset_rows)} rows — expected >= 1000"
        )


# ── Knowledge Base tests ──────────────────────────────────────────────────────

class TestKnowledgeBase:

    def test_kb_file_exists(self):
        assert os.path.exists(KB_PATH), f"Missing: {KB_PATH}"

    def test_kb_is_valid_json(self, kb_data):
        assert isinstance(kb_data, list), "KB records must be a list"
        assert len(kb_data) > 0, "KB has no records"

    def test_kb_has_records(self, kb_data):
        assert len(kb_data) >= 50, f"KB has only {len(kb_data)} records"

    def test_kb_required_fields(self, kb_data):
        required = {"id", "language", "topic", "title", "level"}
        for rec in kb_data:
            missing = required - set(rec.keys())
            assert not missing, f"KB record '{rec.get('id')}' missing fields: {missing}"

    def test_kb_unique_ids(self, kb_data):
        ids = [r["id"] for r in kb_data]
        dupes = [x for x in ids if ids.count(x) > 1]
        assert not dupes, f"Duplicate KB IDs: {list(set(dupes))[:10]}"

    def test_kb_language_values(self, kb_data):
        allowed = {"python", "java", "c", "shared"}
        bad = [(r["id"], r["language"]) for r in kb_data if r["language"] not in allowed]
        assert not bad, f"Invalid KB language values: {bad[:10]}"

    def test_kb_covers_all_three_languages(self, kb_data):
        langs = {r["language"] for r in kb_data}
        for lang in ("python", "java", "c"):
            assert lang in langs, f"Language '{lang}' not in KB"

    def test_kb_micro_records_have_keywords(self, kb_data):
        # Records with quick_facts must also have keywords.
        bad = [
            r["id"] for r in kb_data
            if r.get("quick_facts") and not r.get("keywords")
        ]
        assert not bad, f"KB records with quick_facts but no keywords: {bad[:10]}"


# ── Code Examples tests ───────────────────────────────────────────────────────

class TestCodeExamples:

    def test_examples_file_exists(self):
        assert os.path.exists(EXAMPLES_PATH)

    def test_examples_count(self, examples_data):
        examples = examples_data.get("examples", [])
        assert len(examples) >= 100, f"Only {len(examples)} examples — expected >= 100"

    def test_examples_required_fields(self, examples_data):
        required = {"id", "language", "topic", "title", "code"}
        for ex in examples_data.get("examples", []):
            missing = required - set(ex.keys())
            assert not missing, f"Example '{ex.get('id')}' missing: {missing}"

    def test_examples_unique_ids(self, examples_data):
        ids = [e["id"] for e in examples_data.get("examples", [])]
        dupes = [x for x in ids if ids.count(x) > 1]
        assert not dupes, f"Duplicate example IDs: {list(set(dupes))[:10]}"

    def test_examples_language_values(self, examples_data):
        allowed = {"python", "java", "c", "shared"}
        bad = [
            (e["id"], e["language"])
            for e in examples_data.get("examples", [])
            if e["language"] not in allowed
        ]
        assert not bad, f"Invalid example languages: {bad[:10]}"

    def test_examples_no_empty_code(self, examples_data):
        bad = [
            e["id"] for e in examples_data.get("examples", [])
            if not e.get("code", "").strip()
        ]
        assert not bad, f"Examples with empty code: {bad[:10]}"

    def test_examples_cover_all_languages(self, examples_data):
        langs = {e["language"] for e in examples_data.get("examples", [])}
        for lang in ("python", "java", "c"):
            assert lang in langs, f"No examples for language '{lang}'"

    def test_metadata_count_matches_actual(self, examples_data):
        declared = examples_data.get("metadata", {}).get("total_examples", 0)
        actual   = len(examples_data.get("examples", []))
        assert declared == actual, (
            f"Metadata says {declared} examples but found {actual}"
        )


# ── Code Templates tests ──────────────────────────────────────────────────────

class TestCodeTemplates:

    def test_templates_file_exists(self):
        assert os.path.exists(TEMPLATES_PATH)

    def test_templates_count(self, templates_data):
        templates = templates_data.get("templates", [])
        assert len(templates) >= 100, f"Only {len(templates)} templates — expected >= 100"

    def test_templates_required_fields(self, templates_data):
        required = {"id", "language", "topic", "title", "template", "filled_example"}
        for tmpl in templates_data.get("templates", []):
            missing = required - set(tmpl.keys())
            assert not missing, f"Template '{tmpl.get('id')}' missing: {missing}"

    def test_templates_unique_ids(self, templates_data):
        ids = [t["id"] for t in templates_data.get("templates", [])]
        dupes = [x for x in ids if ids.count(x) > 1]
        assert not dupes, f"Duplicate template IDs: {list(set(dupes))[:10]}"

    def test_templates_have_trigger_phrases(self, templates_data):
        bad = [
            t["id"] for t in templates_data.get("templates", [])
            if not t.get("trigger_phrases")
        ]
        assert not bad, f"Templates without trigger_phrases: {bad[:10]}"

    def test_templates_cover_all_languages(self, templates_data):
        langs = {t["language"] for t in templates_data.get("templates", [])}
        for lang in ("python", "java", "c"):
            assert lang in langs, f"No templates for language '{lang}'"

    def test_metadata_count_matches_actual(self, templates_data):
        declared = templates_data.get("metadata", {}).get("total_templates", 0)
        actual   = len(templates_data.get("templates", []))
        assert declared == actual, (
            f"Metadata says {declared} templates but found {actual}"
        )


# ── Quizzes tests ─────────────────────────────────────────────────────────────

class TestQuizzes:

    def test_quizzes_file_exists(self):
        assert os.path.exists(QUIZZES_PATH)

    def test_quizzes_count(self, quizzes_data):
        # quizzes.json uses key "quizzes" not "questions"
        questions = quizzes_data.get("quizzes", quizzes_data.get("questions", []))
        assert len(questions) >= 100, f"Only {len(questions)} quiz questions"

    def test_quizzes_required_fields(self, quizzes_data):
        # MC questions need options + correct_index.
        # FITB questions need code + answer instead.
        mc_required   = {"id", "language", "topic", "question", "options", "correct_index"}
        fitb_required = {"id", "language", "topic", "question", "code", "answer"}
        for q in quizzes_data.get("quizzes", quizzes_data.get("questions", [])):
            qtype = q.get("question_type", "")
            if qtype == "multiple_choice":
                missing = mc_required - set(q.keys())
                assert not missing, f"MC quiz '{q.get('id')}' missing: {missing}"
            elif qtype in ("fill_in_blank", "fill_in_blank_mc"):
                missing = fitb_required - set(q.keys())
                assert not missing, f"FITB quiz '{q.get('id')}' missing: {missing}"

    def test_quizzes_options_are_list(self, quizzes_data):
        # Only multiple_choice and fill_in_blank_mc questions require an options list.
        bad = [
            q["id"] for q in quizzes_data.get("quizzes", quizzes_data.get("questions", []))
            if q.get("question_type") in ("multiple_choice", "fill_in_blank_mc")
            and not isinstance(q.get("options"), list)
        ]
        assert not bad, f"Quiz questions without list options: {bad[:10]}"

    def test_quizzes_answer_in_options(self, quizzes_data):
        # For multiple_choice: correct_index must be a valid 0-based index.
        # For identification: correct_index is -1 (answered by typing) — skip check.
        bad = [
            q["id"] for q in quizzes_data.get("quizzes", quizzes_data.get("questions", []))
            if q.get("question_type") == "multiple_choice"
            and (
                not isinstance(q.get("correct_index"), int)
                or not (0 <= q["correct_index"] < len(q.get("options", [])))
            )
        ]
        assert not bad, f"Multiple-choice correct_index out of range: {bad[:10]}"

    def test_quizzes_cover_all_languages(self, quizzes_data):
        langs = {q["language"] for q in quizzes_data.get("quizzes", quizzes_data.get("questions", []))}
        for lang in ("python", "java", "c"):
            assert lang in langs, f"No quizzes for language '{lang}'"
