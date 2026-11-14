import os
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

def _utcnow():
    return datetime.now(timezone.utc).isoformat()

def _conn():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Add it to your .env file or Railway environment."
        )
    return psycopg2.connect(database_url)

def init_users_table():
    c = _conn()
    cur = c.cursor()
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
    c.commit()
    cur.close()
    c.close()

def upsert_user(google_id, email, display_name, picture=None):
    now = _utcnow()
    c   = _conn()
    cur = c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id FROM users WHERE google_id = %s", (google_id,))
    row = cur.fetchone()
    if row:
        cur.execute(
            "UPDATE users SET email=%s, display_name=%s, picture=%s, last_login=%s WHERE google_id=%s",
            (email, display_name, picture, now, google_id),
        )
        user_id = row["id"]
    else:
        cur.execute(
            "INSERT INTO users (google_id, email, display_name, picture, created_at, last_login) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (google_id, email, display_name, picture, now, now),
        )
        user_id = cur.fetchone()["id"]
    c.commit()
    cur.close()
    c.close()
    return user_id

def get_user_by_id(user_id):
    c   = _conn()
    cur = c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    row = cur.fetchone()
    cur.close()
    c.close()
    return dict(row) if row else None

def get_user_by_google_id(google_id):
    c   = _conn()
    cur = c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM users WHERE google_id = %s", (google_id,))
    row = cur.fetchone()
    cur.close()
    c.close()
    return dict(row) if row else None
