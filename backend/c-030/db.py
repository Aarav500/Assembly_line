import os
import sqlite3
from flask import current_app, g

DB_NAME = os.environ.get("DB_NAME", "app.db")

def get_db():
    if "db" not in g:
        db_path = os.path.join(current_app.instance_path, DB_NAME)
        g.db = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES, check_same_thread=False)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            comment TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    db.commit()


def insert_entry(name: str, email: str, comment: str) -> int:
    db = get_db()
    cur = db.execute(
        "INSERT INTO entries (name, email, comment) VALUES (?, ?, ?)",
        (name, email, comment),
    )
    db.commit()
    return cur.lastrowid


def query_entries(limit: int = 10):
    db = get_db()
    cur = db.execute(
        "SELECT id, name, email, comment, created_at FROM entries ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )
    return cur.fetchall()

