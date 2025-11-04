import time
from contextlib import contextmanager
from urllib.parse import urlparse

from flask import current_app
from sqlalchemy import create_engine, text, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

from monitoring.metrics import (
    db_checkouts_total,
    db_checkout_errors_total,
    db_connections_created_total,
)


def _build_engine(config) -> Engine:
    db_url = config.get("DATABASE_URL")
    parsed = urlparse(db_url)
    is_sqlite = parsed.scheme.startswith("sqlite")

    engine_kwargs = {}
    poolclass = QueuePool
    if is_sqlite:
        # SQLite has limited pooling relevance; still configure
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    engine_kwargs.update(
        poolclass=poolclass,
        pool_size=config.get("DB_POOL_SIZE", 10),
        max_overflow=config.get("DB_MAX_OVERFLOW", 5),
        pool_timeout=config.get("DB_POOL_TIMEOUT", 30),
        future=True,
    )

    engine = create_engine(db_url, **engine_kwargs)

    # Instrument pool events
    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_conn, conn_record):  # noqa: ARG001
        db_connections_created_total.inc()

    @event.listens_for(engine, "checkout")
    def _on_checkout(dbapi_conn, conn_record, conn_proxy):  # noqa: ARG001
        db_checkouts_total.inc()

    @event.listens_for(engine, "checkout")
    def _checkout_timer(dbapi_conn, conn_record, conn_proxy):  # noqa: ARG001
        # Placeholder hook if timing around checkout is desired in future
        pass

    @event.listens_for(engine, "checkin")
    def _on_checkin(dbapi_conn, conn_record):  # noqa: ARG001
        # Gauges updated at scrape time
        pass

    return engine


def init_db(app):
    engine = _build_engine(app.config)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    app.extensions["db_engine"] = engine
    app.extensions["db_sessionmaker"] = SessionLocal


def shutdown_db(app):
    engine: Engine = app.extensions.get("db_engine")
    if engine:
        engine.dispose(close=True)


def get_session() -> Session:
    SessionLocal = current_app.extensions.get("db_sessionmaker")
    if SessionLocal is None:
        raise RuntimeError("Database not initialized")
    return SessionLocal()


@contextmanager
def session_scope() -> Session:
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        db_checkout_errors_total.inc()
        raise
    finally:
        session.close()


def ping_db(timeout: float = 3.0) -> bool:
    engine: Engine = current_app.extensions.get("db_engine")
    if engine is None:
        return False
    start = time.perf_counter()
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return (time.perf_counter() - start) <= timeout
    except Exception:
        return False


def example_query() -> dict:
    # Simple cross-dialect check
    with session_scope() as s:
        try:
            result = s.execute(text("SELECT 1 AS value"))
            row = result.mappings().first()
            return {"value": row["value"] if row else None}
        except Exception as exc:
            return {"error": str(exc)}

