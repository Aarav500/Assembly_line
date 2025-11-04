import os
from typing import Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")


def create_engine_from_url(url: Optional[str] = None):
    url = url or get_database_url()
    engine = create_engine(url, future=True)
    return engine


def create_session_factory(engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=True, autocommit=False, expire_on_commit=False, future=True)

