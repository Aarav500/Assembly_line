import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm import declarative_base

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///app.db")

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, echo=False, future=True, connect_args=connect_args)
SessionLocal = scoped_session(sessionmaker(bind=engine, autocommit=False, autoflush=False))
Base = declarative_base()

def init_db():
    from models import Event, AlertRule, Alert  # noqa: F401
    Base.metadata.create_all(bind=engine)

