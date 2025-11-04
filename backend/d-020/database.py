from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base
from config import Config

_config = Config()
engine = create_engine(_config.DATABASE_URL, echo=False, future=True)
SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False))
Base = declarative_base()


def init_db():
    from models import UsageEvent, Pricing  # noqa: F401
    Base.metadata.create_all(bind=engine)

