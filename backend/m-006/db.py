import os
import sqlite3
import threading
import json
from flask import g

_db_lock = threading.Lock()


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


def get_db(db_path):
    if 'db' not in g:
        os.makedirs(os.path.dirname(db_path) or '.', exist_ok=True)
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = dict_factory
        # Enable useful pragmas
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('PRAGMA journal_mode = WAL')
        g.db = conn
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db(db_path):
    with _db_lock:
        conn = sqlite3.connect(db_path)
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('PRAGMA journal_mode = WAL')
        # Create base table
        conn.execute(
            '''CREATE TABLE IF NOT EXISTS snippets (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   title TEXT NOT NULL,
                   content TEXT NOT NULL,
                   tags TEXT,
                   language TEXT,
                   framework TEXT,
                   source TEXT,
                   file_path TEXT,
                   symbol TEXT,
                   project TEXT,
                   pinned INTEGER DEFAULT 0,
                   created_at TEXT NOT NULL,
                   updated_at TEXT NOT NULL
               )'''
        )
        # Create FTS5 virtual table for searching
        # Using external content pattern managed by app (manual sync)
        conn.execute(
            '''CREATE VIRTUAL TABLE IF NOT EXISTS snippets_fts USING fts5(
                   title, content, tags, language, framework, file_path, symbol, project,
                   tokenize = 'porter'
               )'''
        )
        # Indices to speed filters
        conn.execute('CREATE INDEX IF NOT EXISTS idx_snippets_language ON snippets(language)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_snippets_project ON snippets(project)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_snippets_framework ON snippets(framework)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_snippets_pinned ON snippets(pinned)')
        conn.commit()
        conn.close()


def row_to_dict(row):
    if row is None:
        return None
    d = dict(row)
    # normalize tags
    tags_json = d.get('tags')
    if tags_json:
        try:
            d['tags'] = json.loads(tags_json)
        except Exception:
            d['tags'] = []
    else:
        d['tags'] = []
    # ensure pinned as bool
    d['pinned'] = bool(d.get('pinned', 0))
    return d

