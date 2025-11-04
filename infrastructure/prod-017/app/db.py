import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase


class Base(DeclarativeBase):
    pass


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        # Example fallback. Replace with your env or config.
        url = "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"
    return url


engine = create_engine(get_database_url(), pool_pre_ping=True, pool_size=5, max_overflow=5)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

