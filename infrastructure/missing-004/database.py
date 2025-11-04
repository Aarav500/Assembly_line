from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker, declarative_base
from config import settings

engine = create_engine(settings.DATABASE_URL, future=True, echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
db_session = scoped_session(SessionLocal)

Base = declarative_base()


def init_db():
    from models import EmailMessage, EventLog, Unsubscribe  # noqa: F401
    Base.metadata.create_all(bind=engine)


__all__ = ["engine", "db_session", "Base", "init_db"]

