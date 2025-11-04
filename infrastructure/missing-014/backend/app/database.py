from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .config import settings


def _engine_kwargs(url: str):
    kwargs = {}
    if url.startswith("sqlite"):  # SQLite needs this in multi-threaded ASGI
        kwargs["connect_args"] = {"check_same_thread": False}
    return kwargs


engine = create_engine(settings.DATABASE_URL, **_engine_kwargs(settings.DATABASE_URL))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

