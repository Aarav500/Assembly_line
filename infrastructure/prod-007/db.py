import sqlite3
from typing import Any, Dict, List, Optional, Tuple
from flask import current_app, g


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        db_path = current_app.config["DATABASE"]
        conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db  # type: ignore[return-value]


def close_db(e: Optional[BaseException]) -> None:
    db: Optional[sqlite3.Connection] = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    db = get_db()
    db.executescript(
        """
        PRAGMA journal_mode=WAL;
        PRAGMA foreign_keys=ON;

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            bio TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_posts_title ON posts(title);
        CREATE INDEX IF NOT EXISTS idx_posts_content ON posts(content);
        """
    )
    db.commit()


def create_user(db: sqlite3.Connection, *, username: str, email: str, bio: str) -> int:
    cur = db.execute(
        "INSERT INTO users (username, email, bio) VALUES (?, ?, ?)",
        (username, email, bio),
    )
    db.commit()
    return int(cur.lastrowid)


def get_user_by_username(db: sqlite3.Connection, username: str) -> Optional[Dict[str, Any]]:
    cur = db.execute("SELECT id, username, email, bio FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    return dict(row) if row else None


def create_post(db: sqlite3.Connection, *, user_id: int, title: str, content: str) -> int:
    cur = db.execute(
        "INSERT INTO posts (user_id, title, content) VALUES (?, ?, ?)",
        (user_id, title, content),
    )
    db.commit()
    return int(cur.lastrowid)


def search_posts(db: sqlite3.Connection, pattern: str, escape_char: str) -> List[Dict[str, Any]]:
    # Parameterized LIKE with explicit ESCAPE to avoid wildcard injection
    sql = (
        f"SELECT p.id, p.title, p.content, p.created_at, u.username as author "
        f"FROM posts p JOIN users u ON p.user_id = u.id "
        f"WHERE p.title LIKE ? ESCAPE '{escape_char}' OR p.content LIKE ? ESCAPE '{escape_char}' "
        f"ORDER BY p.created_at DESC LIMIT 50"
    )
    cur = db.execute(sql, (pattern, pattern))
    rows = cur.fetchall()
    return [dict(r) for r in rows]

