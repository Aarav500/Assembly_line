import os
import sqlite3
from flask import g
from typing import Optional

_DB_SCHEMA = r"""
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY,
    ts INTEGER NOT NULL,
    ts_iso TEXT NOT NULL,
    level TEXT,
    message TEXT NOT NULL,
    service TEXT,
    environment TEXT,
    user_id TEXT,
    request_id TEXT,
    host TEXT,
    app_version TEXT,
    logger_name TEXT,
    thread_name TEXT,
    extra_json TEXT,
    search_text TEXT
);

-- Full-text search index on aggregated search_text
CREATE VIRTUAL TABLE IF NOT EXISTS logs_fts USING fts5(
    search_text, content='logs', content_rowid='id', tokenize='porter'
);

CREATE TRIGGER IF NOT EXISTS logs_ai AFTER INSERT ON logs BEGIN
    INSERT INTO logs_fts(rowid, search_text) VALUES (new.id, new.search_text);
END;

CREATE TRIGGER IF NOT EXISTS logs_ad AFTER DELETE ON logs BEGIN
    DELETE FROM logs_fts WHERE rowid = old.id;
END;

CREATE TRIGGER IF NOT EXISTS logs_au AFTER UPDATE OF search_text ON logs BEGIN
    UPDATE logs_fts SET search_text = new.search_text WHERE rowid = new.id;
END;
"""


def get_db() -> sqlite3.Connection:
    db = getattr(g, '_db_conn', None)
    if db is None:
        db_path = g.get('db_path') or getattr(g, 'app', None)
        db_file = g.get('DB_PATH') if hasattr(g, 'DB_PATH') else None
        # Our app sets config on flask app; fallback to default
        db_file = db_file or getattr(g, 'db_file', None)
        if not db_file:
            # Fallback to env or default
            db_file = os.environ.get('LOGS_DB', os.path.join(os.getcwd(), 'logs.db'))
        db = sqlite3.connect(db_file, detect_types=sqlite3.PARSE_DECLTYPES, check_same_thread=False)
        db.row_factory = sqlite3.Row
        g._db_conn = db
    return db


def close_db(e: Optional[BaseException] = None):
    db = getattr(g, '_db_conn', None)
    if db is not None:
        db.close()
        g._db_conn = None


def init_db(db_path: str):
    # Ensure directory exists
    os.makedirs(os.path.dirname(db_path) or '.', exist_ok=True)
    conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
    try:
        conn.executescript(_DB_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def ensure_db_initialized(db_path: str):
    # Lazy-create schema when first requested
    if not hasattr(g, '_db_initialized'):
        init_db(db_path)
        g._db_initialized = True
        # Also stash DB_PATH so get_db can find it
        g.DB_PATH = db_path

