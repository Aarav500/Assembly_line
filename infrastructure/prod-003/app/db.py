from __future__ import annotations

import logging
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from . import config

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


engine: Engine = create_engine(
    config.DATABASE_URL,
    echo=config.DB_ECHO,
    pool_size=config.DB_POOL_SIZE,
    max_overflow=config.DB_MAX_OVERFLOW,
    pool_recycle=config.DB_POOL_RECYCLE,
    pool_timeout=config.DB_POOL_TIMEOUT,
    pool_pre_ping=True,
    connect_args={"connect_timeout": config.DB_CONNECT_TIMEOUT},
)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


@contextmanager
def session_scope() -> Session:
    session: Session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ping() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError as exc:
        logger.debug("DB ping failed: %s", exc)
        return False

