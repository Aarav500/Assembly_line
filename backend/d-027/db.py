from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import Config

engine = create_engine(Config.METADB_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

@contextmanager
def get_session():
    session = SessionLocal()
    try:
      yield session
      session.commit()
    except Exception:
      session.rollback()
      raise
    finally:
      session.close()

