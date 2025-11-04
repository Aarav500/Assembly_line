import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///data.db")

engine = create_engine(
    DATABASE_URL,
    future=True,
    echo=False,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = scoped_session(
    sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
)

Base = declarative_base()


def init_db():
    from models import Service, Measurement, Incident, DailyReport  # noqa
    Base.metadata.create_all(bind=engine)

