from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.types import JSON as SAJSON
from datetime import datetime
import json

Base = declarative_base()

class JSONEncodedDict(Text):
    impl = Text

    def bind_processor(self, dialect):
        def process(value):
            if value is None:
                return None
            return json.dumps(value)
        return process

    def result_processor(self, dialect, coltype):
        def process(value):
            if value is None:
                return None
            return json.loads(value)
        return process

class Sandbox(Base):
    __tablename__ = 'sandboxes'

    id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=True)
    template = Column(String(255), nullable=False)
    status = Column(String(64), nullable=False, default='provisioning')
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    provider = Column(String(128), nullable=False)
    provider_data = Column(JSONEncodedDict, nullable=True)
    last_error = Column(Text, nullable=True)

    def touch(self):
        self.updated_at = datetime.utcnow()

