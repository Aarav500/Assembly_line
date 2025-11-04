from datetime import datetime
from sqlalchemy import BigInteger, Column, String, DateTime
from app.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(255), nullable=False)
    # email will be added via migrations in expand/migrate/contract phases
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

