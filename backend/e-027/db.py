from __future__ import annotations
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from settings import settings

_engine: Engine | None = None
_SessionLocal = None

def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=10, future=True)
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _SessionLocal


def fetchone_scalar(sql: str, **params):
    with get_engine().connect() as conn:
        return conn.execute(text(sql), params).scalar()


def fetchall(sql: str, **params):
    with get_engine().connect() as conn:
        return [dict(row._mapping) for row in conn.execute(text(sql), params).fetchall()]


def execute(sql: str, **params):
    with get_engine().begin() as conn:
        conn.execute(text(sql), params)

