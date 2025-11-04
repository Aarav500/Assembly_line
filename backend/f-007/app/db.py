import os
import pathlib
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base
from .config import Config

# Ensure directory for sqlite file
if Config.DATABASE_URL.startswith("sqlite"):
    db_path = Config.DATABASE_URL.replace("sqlite:///", "")
    if db_path and db_path != ":memory:":
        pathlib.Path(db_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(Config.DATABASE_URL, future=True, pool_pre_ping=True)
SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False))
Base = declarative_base()


def init_db():
    from . import models  # noqa: F401 ensure models imported
    Base.metadata.create_all(bind=engine)

