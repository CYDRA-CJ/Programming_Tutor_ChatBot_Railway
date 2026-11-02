# conftest.py
# Shared pytest fixtures for the Programming Tutor Chatbot test suite.
# All test files import from here automatically — no explicit import needed.

import json
import os
import sys
import pytest

# Ensure project root is on sys.path so app can be imported from any directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Database: use DATABASE_URL if set, otherwise fall back to local PostgreSQL
# for local test runs (no SQLite — the app now uses psycopg2 exclusively).
if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = (
        "postgresql://postgres:123456@localhost:5432/Programming_Tutor_ChatBot"
    )


@pytest.fixture(scope="session")
def app():
    # Create the Flask app once for the entire test session.
    # TESTING=True disables error propagation so assertions catch exceptions cleanly.
    from app import create_app
    flask_app = create_app()
    flask_app.config["TESTING"]    = True
    flask_app.config["SECRET_KEY"] = "pytest-test-secret"
    yield flask_app


@pytest.fixture(scope="session")
def client(app):
    # Flask test client — makes HTTP requests without starting a real server.
    with app.test_client() as c:
        yield c


@pytest.fixture(scope="session")
def session_cookie(client):
    # Hit the index route once to create a session cookie.
    # All subsequent /chat requests reuse the same session (for follow-up tests).
    client.get("/")
    return client


def chat(client, message):
    # Helper: POST a message to /chat and return the parsed JSON response.
    response = client.post(
        "/chat",
        data=json.dumps({"message": message}),
        content_type="application/json",
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    return response.get_json()


# Make chat() importable in all test modules.
@pytest.fixture(scope="session")
def chat_fn(client):
    def _chat(message):
        return chat(client, message)
    return _chat


# ── Data file paths ───────────────────────────────────────────────────────────
DATASET_PATH   = os.path.join("data", "intent_dataset.csv")
KB_PATH        = os.path.join("data", "knowledge_base.json")
EXAMPLES_PATH  = os.path.join("data", "code_examples.json")
TEMPLATES_PATH = os.path.join("data", "code_templates.json")
QUIZZES_PATH   = os.path.join("data", "quizzes.json")

# Approved intent labels — 11 intents (debug_code and predict_output removed).
APPROVED_INTENTS = {
    "greeting", "bot_capabilities", "explain_concept", "show_syntax",
    "show_example", "generate_code", "explain_code",
    "compare_concepts", "request_quiz",
    "follow_up", "clarification",
}

# Approved language tag values.
APPROVED_LANGUAGES = {"python", "java", "c", "multiple", "unspecified"}
