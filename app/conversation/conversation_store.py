import json
import os
import uuid
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras


def _utcnow():
    # Python 3.12+ deprecates datetime.utcnow() — use timezone-aware UTC instead.
    return datetime.now(timezone.utc).isoformat()


# ── Database connection ───────────────────────────────────────────────────────

def _get_connection():
    """Return a psycopg2 connection using DATABASE_URL env var."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Add it to your .env file or Railway environment."
        )
    conn = psycopg2.connect(database_url)
    return conn


def init_db():
    """Create the tables if they don't exist (runs on app startup)."""
    conn = _get_connection()
    cur  = conn.cursor()

    # users table must exist before sessions (foreign key reference)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id           SERIAL PRIMARY KEY,
            google_id    TEXT    NOT NULL UNIQUE,
            email        TEXT    NOT NULL,
            display_name TEXT    NOT NULL,
            picture      TEXT,
            created_at   TEXT    NOT NULL,
            last_login   TEXT    NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id     TEXT PRIMARY KEY,
            created_at     TEXT NOT NULL,
            updated_at     TEXT NOT NULL,
            user_id        INTEGER REFERENCES users(id),
            title_override TEXT,
            pinned         INTEGER NOT NULL DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id         SERIAL PRIMARY KEY,
            session_id TEXT NOT NULL,
            role       TEXT NOT NULL,
            content    TEXT NOT NULL,
            intent     TEXT,
            language   TEXT,
            topic      TEXT,
            timestamp  TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS contexts (
            session_id TEXT PRIMARY KEY,
            data       TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # Indexes (IF NOT EXISTS is supported in PostgreSQL 9.5+)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id)")

    conn.commit()
    cur.close()
    conn.close()


# ── Sessions ──────────────────────────────────────────────────────────────────

def new_session(user_id=None):
    session_id = str(uuid.uuid4())
    now        = _utcnow()
    conn       = _get_connection()
    cur        = conn.cursor()
    cur.execute(
        "INSERT INTO sessions (session_id, created_at, updated_at, user_id) VALUES (%s, %s, %s, %s)",
        (session_id, now, now, user_id),
    )
    conn.commit()
    cur.close()
    conn.close()
    return session_id


def session_exists(session_id):
    """Return True if the session_id exists in the database."""
    if not session_id:
        return False
    conn = _get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT 1 FROM sessions WHERE session_id = %s", (session_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row is not None


def get_title(session_id, max_len=40):
    """Return title_override if set, else the first user message (truncated)."""
    conn = _get_connection()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT title_override FROM sessions WHERE session_id = %s", (session_id,))
    row = cur.fetchone()
    if row and row["title_override"]:
        cur.close()
        conn.close()
        t = row["title_override"].strip()
        return t if len(t) <= max_len else t[:max_len - 1] + "…"
    cur.execute(
        "SELECT content FROM messages WHERE session_id = %s AND role = 'user' "
        "ORDER BY id ASC LIMIT 1",
        (session_id,),
    )
    row2 = cur.fetchone()
    cur.close()
    conn.close()
    if not row2:
        return None
    text = " ".join(row2["content"].split())
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def get_updated_at(session_id):
    conn = _get_connection()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT updated_at FROM sessions WHERE session_id = %s", (session_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row["updated_at"] if row else ""


def get_sessions_for_user(user_id):
    """Return all sessions for a user: pinned first, then newest-first."""
    conn = _get_connection()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT session_id, pinned, title_override, updated_at "
        "FROM sessions WHERE user_id = %s "
        "ORDER BY pinned DESC, updated_at DESC",
        (user_id,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


def rename_session(session_id, new_title):
    """Set a custom title for a session. Pass None to clear the override."""
    conn = _get_connection()
    cur  = conn.cursor()
    cur.execute(
        "UPDATE sessions SET title_override = %s WHERE session_id = %s",
        (new_title.strip() if new_title else None, session_id),
    )
    conn.commit()
    cur.close()
    conn.close()


def pin_session(session_id, pinned=True):
    """Pin or unpin a session."""
    conn = _get_connection()
    cur  = conn.cursor()
    cur.execute(
        "UPDATE sessions SET pinned = %s WHERE session_id = %s",
        (1 if pinned else 0, session_id),
    )
    conn.commit()
    cur.close()
    conn.close()


def claim_sessions(session_ids, user_id):
    """Assign previously anonymous sessions to a user after they log in."""
    if not session_ids or not user_id:
        return
    conn = _get_connection()
    cur  = conn.cursor()
    psycopg2.extras.execute_batch(
        cur,
        "UPDATE sessions SET user_id = %s WHERE session_id = %s AND user_id IS NULL",
        [(user_id, sid) for sid in session_ids],
    )
    conn.commit()
    cur.close()
    conn.close()


def session_belongs_to_user(session_id, user_id):
    """Return True if the session exists and belongs to the given user."""
    conn = _get_connection()
    cur  = conn.cursor()
    cur.execute(
        "SELECT 1 FROM sessions WHERE session_id = %s AND user_id = %s",
        (session_id, user_id),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row is not None


# ── Messages ──────────────────────────────────────────────────────────────────

def save_message(session_id, role, content, intent=None, language=None, topic=None):
    """Save one message turn to the database. role: 'user' or 'assistant'"""
    now  = _utcnow()
    conn = _get_connection()
    cur  = conn.cursor()
    cur.execute(
        """INSERT INTO messages (session_id, role, content, intent, language, topic, timestamp)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (session_id, role, content, intent, language, topic, now),
    )
    cur.execute(
        "UPDATE sessions SET updated_at = %s WHERE session_id = %s",
        (now, session_id),
    )
    conn.commit()
    cur.close()
    conn.close()


def get_history(session_id, limit=20):
    """Return the last `limit` messages for a session as a list of dicts."""
    conn = _get_connection()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """SELECT role, content, intent, language, topic, timestamp
           FROM messages
           WHERE session_id = %s
           ORDER BY id DESC
           LIMIT %s""",
        (session_id, limit),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    # Reverse so oldest message is first.
    return [dict(r) for r in reversed(rows)]


def clear_history(session_id):
    """Delete all messages for a session (clear history)."""
    conn = _get_connection()
    cur  = conn.cursor()
    cur.execute("DELETE FROM messages WHERE session_id = %s", (session_id,))
    conn.commit()
    cur.close()
    conn.close()


# ── Context ───────────────────────────────────────────────────────────────────

def load_context(session_id):
    """Return the saved context dict for a session, or None if there is none yet."""
    conn = _get_connection()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT data FROM contexts WHERE session_id = %s", (session_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None
    try:
        return json.loads(row["data"])
    except (ValueError, TypeError):
        return None


def save_context(session_id, ctx):
    """Insert or update the context for a session (upsert)."""
    conn = _get_connection()
    cur  = conn.cursor()
    cur.execute(
        """INSERT INTO contexts (session_id, data, updated_at) VALUES (%s, %s, %s)
           ON CONFLICT (session_id) DO UPDATE
               SET data = EXCLUDED.data, updated_at = EXCLUDED.updated_at""",
        (session_id, json.dumps(ctx, ensure_ascii=False), _utcnow()),
    )
    conn.commit()
    cur.close()
    conn.close()


def delete_session(session_id):
    """Remove the session, its context and all its messages."""
    conn = _get_connection()
    cur  = conn.cursor()
    cur.execute("DELETE FROM messages WHERE session_id = %s", (session_id,))
    cur.execute("DELETE FROM contexts WHERE session_id = %s", (session_id,))
    cur.execute("DELETE FROM sessions WHERE session_id = %s", (session_id,))
    conn.commit()
    cur.close()
    conn.close()
