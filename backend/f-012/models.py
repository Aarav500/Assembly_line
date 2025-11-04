from sqlalchemy import Column, Integer, Float, Text, Date, DateTime
from sqlalchemy.orm import validates
from datetime import datetime
import json

from db import Base, engine


class CostRecord(Base):
    __tablename__ = 'cost_records'

    id = Column(Integer, primary_key=True)
    date = Column(Date, index=True, nullable=False)
    amount = Column(Float, nullable=False)
    tags_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    @property
    def tags(self):
        if not self.tags_text:
            return {}
        try:
            return json.loads(self.tags_text)
        except Exception:
            return {}

    @tags.setter
    def tags(self, value):
        if value is None:
            self.tags_text = None
        else:
            self.tags_text = json.dumps(value, separators=(",", ":"), sort_keys=True)

    @validates('amount')
    def validate_amount(self, key, value):
        if value is None:
            raise ValueError('amount is required')
        return float(value)


def init_db():
    Base.metadata.create_all(bind=engine)

