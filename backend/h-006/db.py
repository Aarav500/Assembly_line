import os
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker, declarative_base


def _default_db_url():
    return os.getenv("DATABASE_URL", "sqlite:///data.db")


def _engine_kwargs(url: str):
    if url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {}


engine = create_engine(_default_db_url(), **_engine_kwargs(_default_db_url()))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
db_session = scoped_session(SessionLocal)
Base = declarative_base()


def init_db():
    from models import KnowledgeItem, KnowledgeVersion  # noqa: F401
    Base.metadata.create_all(bind=engine)

