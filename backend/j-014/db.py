import sqlite3
from datetime import datetime

DB_PATH = 'scheduler.db'


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            type TEXT,
            params TEXT,
            status TEXT,
            progress INTEGER,
            message TEXT,
            error TEXT,
            created_at TEXT,
            start_at TEXT,
            started_at TEXT,
            finished_at TEXT,
            last_heartbeat TEXT
        )
        '''
    )
    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER,
            ts TEXT,
            level TEXT,
            message TEXT,
            FOREIGN KEY(job_id) REFERENCES jobs(id)
        )
        '''
    )
    cur.execute('CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_logs_job_id ON logs(job_id)')
    conn.commit()
    conn.close()


def utcnow_iso():
    return datetime.utcnow().isoformat()

