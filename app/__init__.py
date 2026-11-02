import os
import json
import joblib
from datetime import timedelta
from flask import Flask
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

# ── Module-level singletons loaded once at startup ───────────────────────────
_classifier_pipeline = None
_knowledge_base       = None
_code_examples        = None
_code_templates       = None
_quizzes              = None


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def create_app():
    # Create and configure the Flask application instance.
    global _classifier_pipeline, _knowledge_base
    global _code_examples, _code_templates, _quizzes

    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
    )

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-prod")
    # Keep sessions alive for 30 days (used by the auth system).
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
    server_name = os.environ.get("SERVER_NAME")
    if server_name:
        # Production / Railway: SERVER_NAME is the public domain (no port needed)
        app.config["SERVER_NAME"] = server_name
        app.config["APPLICATION_ROOT"] = "/"
        app.config["PREFERRED_URL_SCHEME"] = "https"
    else:
        # Local development fallback
        port = os.environ.get("FLASK_PORT", "5000")
        app.config["SERVER_NAME"] = f"localhost:{port}"
        app.config["APPLICATION_ROOT"] = "/"
        app.config["PREFERRED_URL_SCHEME"] = "http"

    # ── Google OAuth via Authlib ──────────────────────────────────────────────
    from authlib.integrations.flask_client import OAuth
    oauth = OAuth(app)
    oauth.register(
        name="google",
        client_id=os.environ.get("GOOGLE_CLIENT_ID"),
        client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={
            "scope": "openid email profile",
            "prompt": "select_account",  
        },
    )

    # ── Paths resolved from project root ─────────────────────────────────────
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    model_path     = os.path.join(root, "models", "classifier.joblib")
    kb_path        = os.path.join(root, "data", "knowledge_base.json")
    ex_path        = os.path.join(root, "data", "code_examples.json")
    tmpl_path      = os.path.join(root, "data", "code_templates.json")
    quiz_path      = os.path.join(root, "data", "quizzes.json")

    # ── Load trained model ────────────────────────────────────────────────────
    if _classifier_pipeline is None:
        _classifier_pipeline = joblib.load(model_path)

    # ── Load content files ────────────────────────────────────────────────────
    if _knowledge_base is None:
        _knowledge_base = _load_json(kb_path)["records"]

    if _code_examples is None:
        _code_examples = _load_json(ex_path)["examples"]

    if _code_templates is None:
        _code_templates = _load_json(tmpl_path)["templates"]

    if _quizzes is None:
        _quizzes = _load_json(quiz_path)["quizzes"]

    # ── Attach to app so routes can access them ───────────────────────────────
    app.classifier   = _classifier_pipeline
    app.kb_records   = _knowledge_base
    app.ex_records   = _code_examples
    app.tmpl_records = _code_templates
    app.quiz_records = _quizzes

    # ── Register blueprints ───────────────────────────────────────────────────
    from app.routes.chat import chat_bp
    from app.routes.auth import auth_bp
    app.register_blueprint(chat_bp)
    app.register_blueprint(auth_bp)

    # ── Initialise users table ────────────────────────────────────────────────
    from app.auth.user_store import init_users_table
    with app.app_context():
        init_users_table()

    return app


def get_classifier():
    return _classifier_pipeline


def get_kb():
    return _knowledge_base


def get_examples():
    return _code_examples


def get_templates():
    return _code_templates


def get_quizzes():
    return _quizzes
