import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///data.db")

connect_args = {}
if DATABASE_URL.startswith("sqlite"):  # pragma: no cover
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, echo=False, future=True, connect_args=connect_args)

Base = declarative_base()

