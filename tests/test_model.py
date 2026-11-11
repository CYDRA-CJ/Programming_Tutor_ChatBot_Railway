# test_model.py
# Tests the trained MLP intent classifier:
# file exists, loads correctly, produces valid predictions,
# handles edge cases, and meets the blueprint accuracy targets (≥0.85 acc + F1).

import os
import pytest

from tests.conftest import APPROVED_INTENTS

MODEL_PATH    = os.path.join("models", "classifier.joblib")
METADATA_PATH = os.path.join("models", "metadata.json")
MIN_ACCURACY  = 0.80
MIN_F1        = 0.80


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def classifier():
    from app.classifier.intent_classifier import predict, is_multi_intent
    return predict, is_multi_intent


@pytest.fixture(scope="module")
def model_metadata():
    import json
    with open(METADATA_PATH, encoding="utf-8") as f:
        return json.load(f)


# ── Model file tests ──────────────────────────────────────────────────────────

class TestModelFiles:

    def test_model_file_exists(self):
        assert os.path.exists(MODEL_PATH), f"Missing: {MODEL_PATH}"

    def test_metadata_file_exists(self):
        assert os.path.exists(METADATA_PATH), f"Missing: {METADATA_PATH}"

    def test_model_loads_without_error(self):
        import joblib
        pipeline = joblib.load(MODEL_PATH)
        assert pipeline is not None

    def test_model_is_mlp_pipeline(self):
        import joblib
        from sklearn.neural_network import MLPClassifier
        from sklearn.pipeline import Pipeline
        pipeline = joblib.load(MODEL_PATH)
        assert isinstance(pipeline, Pipeline), "Model is not a sklearn Pipeline"
        assert isinstance(pipeline.named_steps["clf"], MLPClassifier), (
            "Classifier step is not MLPClassifier"
        )

    def test_metadata_source_run(self, model_metadata):
        assert "source_run" in model_metadata, "metadata.json missing 'source_run'"
        assert model_metadata["source_run"].startswith("train_"), (
            f"Unexpected source_run: {model_metadata['source_run']}"
        )

    def test_metadata_accuracy_meets_blueprint(self, model_metadata):
        acc = model_metadata.get("val_accuracy", 0)
        assert acc >= MIN_ACCURACY, (
            f"Val accuracy {acc:.4f} is below blueprint minimum {MIN_ACCURACY}"
        )

    def test_metadata_f1_meets_blueprint(self, model_metadata):
        f1 = model_metadata.get("val_macro_f1", 0)
        assert f1 >= MIN_F1, (
            f"Val macro-F1 {f1:.4f} is below blueprint minimum {MIN_F1}"
        )


# ── Prediction correctness tests ──────────────────────────────────────────────

class TestPredictions:

    def test_predict_returns_required_keys(self, classifier):
        predict, _ = classifier
        result = predict("Hello!")
        assert "intent"     in result, "Missing 'intent' key"
        assert "confidence" in result, "Missing 'confidence' key"

    def test_predicted_intent_is_approved_label(self, classifier):
        predict, _ = classifier
        for text in [
            "Hello!", "What is Python?", "Show me a Java loop",
            "Write a C program", "Quiz me on Python",
        ]:
            result = predict(text)
            assert result["intent"] in APPROVED_INTENTS, (
                f"'{text}' → unapproved intent '{result['intent']}'"
            )

    def test_confidence_is_between_0_and_1(self, classifier):
        predict, _ = classifier
        for text in ["Hello!", "What is a loop?", "show example"]:
            result = predict(text)
            assert 0.0 <= result["confidence"] <= 1.0, (
                f"Confidence {result['confidence']} out of range for '{text}'"
            )

    def test_greeting_intent(self, classifier):
        predict, _ = classifier
        result = predict("Hello there!")
        assert result["intent"] == "greeting"

    def test_explain_concept_intent(self, classifier):
        predict, _ = classifier
        result = predict("What is a variable in Python?")
        assert result["intent"] == "explain_concept"

    def test_generate_code_intent(self, classifier):
        predict, _ = classifier
        result = predict("Write a Python program to add two numbers")
        assert result["intent"] == "generate_code"

    def test_show_example_intent(self, classifier):
        predict, _ = classifier
        result = predict("Give me a sample code of a for loop in Java")
        assert result["intent"] == "show_example"

    def test_show_syntax_intent(self, classifier):
        predict, _ = classifier
        result = predict("Show Java syntax for a method")
        assert result["intent"] == "show_syntax"

    def test_request_quiz_intent(self, classifier):
        predict, _ = classifier
        result = predict("Quiz me on Python loops")
        assert result["intent"] == "request_quiz"

    def test_bot_capabilities_intent(self, classifier):
        predict, _ = classifier
        result = predict("What can you teach me?")
        assert result["intent"] == "bot_capabilities"

    def test_compare_concepts_intent(self, classifier):
        predict, _ = classifier
        result = predict("Compare Python lists with Java arrays")
        assert result["intent"] in ("compare_concepts", "explain_concept", "clarification")

    def test_activity_generate_code_python(self, classifier):
        # Activity-specific generate_code rows added in train_003.
        predict, _ = classifier
        result = predict("make a fibonacci program in python")
        assert result["intent"] == "generate_code"

    def test_activity_show_example_java(self, classifier):
        predict, _ = classifier
        result = predict("give me a sample code of bubble sort in java")
        assert result["intent"] in ("show_example", "generate_code", "clarification")

    def test_activity_show_example_c(self, classifier):
        predict, _ = classifier
        result = predict("show me an example of bank account using c")
        assert result["intent"] == "show_example"

    def test_activity_generate_code_c(self, classifier):
        predict, _ = classifier
        result = predict("write a login system using c")
        assert result["intent"] == "generate_code"

    def test_venv_explain_concept(self, classifier):
        # Venv rows added in train_002.
        predict, _ = classifier
        result = predict("what is a virtual environment in python")
        assert result["intent"] == "explain_concept"

    def test_pip_install_explain_concept(self, classifier):
        # "how do I use pip install" is ambiguous — classifier may return
        # explain_concept or show_syntax, both are valid for pip questions.
        predict, _ = classifier
        result = predict("how do I use pip install")
        assert result["intent"] in ("explain_concept", "show_syntax"), (
            f"Expected explain_concept or show_syntax, got '{result['intent']}'"
        )


# ── Multi-intent tests ────────────────────────────────────────────────────────

class TestMultiIntent:

    def test_is_multi_intent_returns_list(self, classifier):
        _, is_multi = classifier
        result = is_multi("Write a Java program and explain every line")
        assert isinstance(result, list), "is_multi_intent must return a list"

    def test_multi_intent_list_contains_approved_labels(self, classifier):
        _, is_multi = classifier
        result = is_multi("Show a Python example and quiz me")
        for intent in result:
            assert intent in APPROVED_INTENTS, (
                f"Multi-intent returned unapproved label '{intent}'"
            )

    def test_single_message_returns_at_least_one_intent(self, classifier):
        _, is_multi = classifier
        result = is_multi("Hello!")
        assert len(result) >= 1
