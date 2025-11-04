from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker

Base = declarative_base()
engine = None
SessionLocal = None

db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False))


def init_engine(database_url: str, pool_size: int = 5, max_overflow: int = 10):
    global engine
    engine = create_engine(
        database_url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        future=True,
    )
    return engine


def init_session(bind_engine):
    global SessionLocal
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=bind_engine, future=True)
    db_session.configure(bind=bind_engine)
    return SessionLocal

