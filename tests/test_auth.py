# test_auth.py
# Tests for the Google OAuth authentication routes and user store.

import pytest
from app.auth.user_store import upsert_user, get_user_by_id, get_user_by_google_id


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def auth_client(client):
    # Reuse the session-scoped Flask test client from conftest.
    client.get("/")
    return client


# ── /api/me — guest ───────────────────────────────────────────────────────────

class TestApiMeGuest:

    def test_returns_200(self, auth_client):
        r = auth_client.get("/api/me")
        assert r.status_code == 200

    def test_authenticated_false_when_guest(self, auth_client):
        d = auth_client.get("/api/me").get_json()
        assert d["authenticated"] is False

    def test_no_user_fields_when_guest(self, auth_client):
        d = auth_client.get("/api/me").get_json()
        assert "email" not in d
        assert "display_name" not in d


# ── /api/me — logged in ───────────────────────────────────────────────────────

class TestApiMeLoggedIn:

    @pytest.fixture(autouse=True)
    def inject_user(self, auth_client):
        # Create a test user and inject their id into the session.
        uid = upsert_user("google_pytest_001", "pytest@example.com", "Pytest User", None)
        with auth_client.session_transaction() as sess:
            sess["user_id"] = uid
        yield
        # Clean up: remove user_id from session after each test.
        with auth_client.session_transaction() as sess:
            sess.pop("user_id", None)

    def test_authenticated_true(self, auth_client):
        d = auth_client.get("/api/me").get_json()
        assert d["authenticated"] is True

    def test_returns_display_name(self, auth_client):
        d = auth_client.get("/api/me").get_json()
        assert d["display_name"] == "Pytest User"

    def test_returns_email(self, auth_client):
        d = auth_client.get("/api/me").get_json()
        assert d["email"] == "pytest@example.com"

    def test_returns_username_derived_from_email(self, auth_client):
        d = auth_client.get("/api/me").get_json()
        assert d["username"] == "pytest"


# ── /login ────────────────────────────────────────────────────────────────────

class TestLoginRoute:

    def test_login_redirects(self, auth_client):
        # /login should redirect to Google (302) — not 200 or 404.
        r = auth_client.get("/login")
        assert r.status_code == 302

    def test_login_location_is_google(self, auth_client):
        r = auth_client.get("/login")
        location = r.headers.get("Location", "")
        # The redirect URL should point to Google's OAuth endpoint.
        assert "google" in location.lower() or "accounts" in location.lower()


# ── /logout ───────────────────────────────────────────────────────────────────

class TestLogoutRoute:

    def test_logout_redirects(self, auth_client):
        r = auth_client.post("/logout")
        assert r.status_code == 302

    def test_logout_clears_session(self, auth_client):
        # Log in a test user then log out — /api/me should return guest.
        uid = upsert_user("google_pytest_002", "logout@example.com", "Logout User", None)
        with auth_client.session_transaction() as sess:
            sess["user_id"] = uid
        auth_client.post("/logout")
        d = auth_client.get("/api/me").get_json()
        assert d["authenticated"] is False


# ── user_store ────────────────────────────────────────────────────────────────

class TestUserStore:

    def test_upsert_creates_new_user(self):
        uid = upsert_user("google_store_001", "store1@example.com", "Store User One", None)
        assert isinstance(uid, int)
        assert uid > 0

    def test_get_user_by_id(self):
        uid  = upsert_user("google_store_002", "store2@example.com", "Store User Two", None)
        user = get_user_by_id(uid)
        assert user is not None
        assert user["email"] == "store2@example.com"
        assert user["display_name"] == "Store User Two"

    def test_get_user_by_google_id(self):
        upsert_user("google_store_003", "store3@example.com", "Store User Three", None)
        user = get_user_by_google_id("google_store_003")
        assert user is not None
        assert user["email"] == "store3@example.com"

    def test_upsert_updates_existing_user(self):
        # First insert.
        uid1 = upsert_user("google_store_004", "store4@example.com", "Original Name", None)
        # Second call with same google_id but new name — should update, not insert.
        uid2 = upsert_user("google_store_004", "store4@example.com", "Updated Name", None)
        assert uid1 == uid2
        user = get_user_by_id(uid1)
        assert user["display_name"] == "Updated Name"

    def test_upsert_updates_picture(self):
        uid  = upsert_user("google_store_005", "store5@example.com", "Pic User",
                           "https://example.com/old.jpg")
        upsert_user("google_store_005", "store5@example.com", "Pic User",
                    "https://example.com/new.jpg")
        user = get_user_by_id(uid)
        assert user["picture"] == "https://example.com/new.jpg"

    def test_get_nonexistent_user_returns_none(self):
        assert get_user_by_id(999999) is None
        assert get_user_by_google_id("nonexistent_id") is None
