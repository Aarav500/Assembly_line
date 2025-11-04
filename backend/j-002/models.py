from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, Boolean, Float
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime


db = SQLAlchemy()


class Prompt(db.Model):
    __tablename__ = 'prompts'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    default_version_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('prompt_versions.id'), nullable=True)

    versions = relationship('PromptVersion', back_populates='prompt', order_by='PromptVersion.version_number', cascade='all, delete-orphan')
    runs = relationship('RunHistory', back_populates='prompt', cascade='all, delete-orphan')


class PromptVersion(db.Model):
    __tablename__ = 'prompt_versions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prompt_id: Mapped[int] = mapped_column(Integer, ForeignKey('prompts.id'), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    prompt = relationship('Prompt', back_populates='versions')
    runs = relationship('RunHistory', back_populates='version', cascade='all, delete-orphan')


class RunHistory(db.Model):
    __tablename__ = 'run_history'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prompt_id: Mapped[int] = mapped_column(Integer, ForeignKey('prompts.id'), nullable=False)
    prompt_version_id: Mapped[int] = mapped_column(Integer, ForeignKey('prompt_versions.id'), nullable=False)
    input_text: Mapped[str] = mapped_column(Text, default='')
    output_text: Mapped[str] = mapped_column(Text, default='')
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    tokens_prompt: Mapped[int] = mapped_column(Integer, default=0)
    tokens_output: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    parameters = db.Column(db.JSON, default=dict)
    model_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    prompt = relationship('Prompt', back_populates='runs')
    version = relationship('PromptVersion', back_populates='runs')

