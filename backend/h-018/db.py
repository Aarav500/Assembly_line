from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import Settings
from models import Base

_engine = None
SessionLocal = None


def init_db():
    global _engine, SessionLocal
    settings = Settings()
    _engine = create_engine(settings.DB_URL, connect_args={"check_same_thread": False} if settings.DB_URL.startswith("sqlite") else {})
    SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    Base.metadata.create_all(_engine)


def get_engine():
    return _engine

