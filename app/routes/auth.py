import os
from flask import (
    Blueprint, redirect, url_for, session,
    jsonify, request, current_app,
)
from app.auth.user_store import upsert_user, get_user_by_id

auth_bp = Blueprint("auth", __name__)

# Session key that holds the logged-in user's internal database id.
_SESSION_USER_KEY = "user_id"


# ── Helpers ───────────────────────────────────────────────────────────────────

def current_user():
    # Return the user dict for the logged-in user, or None.
    uid = session.get(_SESSION_USER_KEY)
    if not uid:
        return None
    return get_user_by_id(uid)


def login_user(user_id):
    session[_SESSION_USER_KEY] = user_id
    # Keep the session alive for 30 days (Flask default is browser-session).
    session.permanent = True


def logout_user():
    session.pop(_SESSION_USER_KEY, None)


# ── Routes ────────────────────────────────────────────────────────────────────

@auth_bp.route("/login")
def login():
    # Kick off the OAuth flow — redirect the browser to Google.
    oauth = current_app.extensions["authlib.integrations.flask_client"]
    google = oauth.create_client("google")
    # After Google approves, it will call /auth/google/callback.
    redirect_uri = url_for("auth.google_callback", _external=True)
    return google.authorize_redirect(redirect_uri)


@auth_bp.route("/auth/google/callback")
def google_callback():
    # Google redirected here with an authorization code.
    # Exchange the code for a token, fetch the user's profile, save to DB.
    oauth  = current_app.extensions["authlib.integrations.flask_client"]
    google = oauth.create_client("google")

    try:
        token = google.authorize_access_token()
    except Exception:
        # User denied access or something went wrong — go back home quietly.
        return redirect("/")

    # The userinfo is embedded in the id_token (JWT) — no extra HTTP call needed.
    user_info = token.get("userinfo") or {}

    google_id    = user_info.get("sub", "")
    email        = user_info.get("email", "")
    display_name = user_info.get("name") or user_info.get("email", "User")
    picture      = user_info.get("picture")

    if not google_id or not email:
        # Incomplete profile — send them home without logging in.
        return redirect("/")

    # Upsert into the users table and get the internal id.
    user_id = upsert_user(google_id, email, display_name, picture)
    login_user(user_id)

    # Claim any anonymous sessions this browser created before logging in.
    # This links their chat history to the account so it persists across devices.
    from app.conversation.conversation_store import claim_sessions
    anonymous_sessions = session.get("owned", [])
    if anonymous_sessions:
        claim_sessions(anonymous_sessions, user_id)

    return redirect("/")


@auth_bp.route("/logout", methods=["POST", "GET"])
def logout():
    # Browser-initiated logout (GET or POST from a link/form) — redirect to /.
    logout_user()
    return redirect("/")


@auth_bp.route("/api/logout", methods=["POST"])
def api_logout():
    # JS-initiated logout (fetch POST from chat.js) — return JSON, not a redirect.
    # chat.js handles the redirect itself after receiving a 200.
    logout_user()
    return jsonify({"status": "logged_out"}), 200


@auth_bp.route("/api/me")
def api_me():
    # Called by chat.js on every page load to determine login state.
    # Returns:
    #   {authenticated: true,  display_name, email, picture}  — if logged in
    #   {authenticated: false}                                 — if guest
    user = current_user()
    if user:
        return jsonify({
            "authenticated": True,
            "display_name":  user["display_name"],
            "email":         user["email"],
            "picture":       user["picture"],
            "username":      user["email"].split("@")[0],
        }), 200
    return jsonify({"authenticated": False}), 200
