-- schema.sql
-- SQLite database schema for the Programming Language Tutor Chatbot.
-- Database file: data/conversations.db
--
-- This file is for documentation and reference only.
-- The database is created automatically when the Flask app starts for the first time.
-- The creation code is in: app/conversation/conversation_store.py  (sessions, messages, contexts)
--                          app/auth/user_store.py                  (users)
--
-- To recreate the database from scratch:
--   1. Delete data/conversations.db
--   2. Run the Flask app: python main.py
--   The app will recreate it automatically on first request.


-- ── users ────────────────────────────────────────────────────────────────────
-- Stores Google OAuth users who log in to save their conversation history.
-- Guest users are NOT stored here — their sessions are cookie-based only.
CREATE TABLE IF NOT EXISTS users (
    id           INTEGER  PRIMARY KEY AUTOINCREMENT,   -- internal user ID
    google_id    TEXT     NOT NULL UNIQUE,             -- Google account ID
    email        TEXT     NOT NULL,                    -- user email from Google
    display_name TEXT     NOT NULL,                    -- full name from Google
    picture      TEXT,                                 -- profile photo URL (optional)
    created_at   TEXT     NOT NULL,                    -- ISO 8601 timestamp
    last_login   TEXT     NOT NULL                     -- ISO 8601 timestamp
);


-- ── sessions ─────────────────────────────────────────────────────────────────
-- One row per conversation session (each "New conversation" creates a new session).
-- Guests have sessions too, but user_id is NULL and they are not shown in history.
CREATE TABLE IF NOT EXISTS sessions (
    session_id     TEXT     PRIMARY KEY,               -- UUID for the session
    created_at     TEXT     NOT NULL,                  -- ISO 8601 timestamp
    updated_at     TEXT     NOT NULL,                  -- last message time
    user_id        INTEGER  REFERENCES users(id),      -- NULL for guests
    title_override TEXT,                               -- custom name set by user (optional)
    pinned         INTEGER  NOT NULL DEFAULT 0         -- 1 = pinned in sidebar, 0 = normal
);

CREATE INDEX IF NOT EXISTS idx_sessions_user
    ON sessions(user_id);


-- ── messages ─────────────────────────────────────────────────────────────────
-- Every chat message (both user and bot) is stored here.
-- role: "user" = message sent by the student
--       "assistant" = message sent by the chatbot
CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER  PRIMARY KEY AUTOINCREMENT,     -- auto-increment row ID
    session_id TEXT     NOT NULL,                      -- which conversation this belongs to
    role       TEXT     NOT NULL,                      -- "user" or "assistant"
    content    TEXT     NOT NULL,                      -- the message text
    intent     TEXT,                                   -- chatbot intent (e.g. explain_concept)
    language   TEXT,                                   -- detected language (python/java/c)
    topic      TEXT,                                   -- detected topic (e.g. loops)
    timestamp  TEXT     NOT NULL,                      -- ISO 8601 timestamp
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE INDEX IF NOT EXISTS idx_messages_session
    ON messages(session_id, id);


-- ── contexts ─────────────────────────────────────────────────────────────────
-- Stores the conversation context (memory) for each session as serialized JSON.
-- This is what allows the chatbot to remember the previous turn and handle
-- follow-up questions, language switches, and context-aware responses.
-- One row per session — overwritten on every turn.
CREATE TABLE IF NOT EXISTS contexts (
    session_id TEXT     PRIMARY KEY,                   -- matches sessions.session_id
    data       TEXT     NOT NULL,                      -- JSON blob with full context state
    updated_at TEXT     NOT NULL                       -- last updated timestamp
);
