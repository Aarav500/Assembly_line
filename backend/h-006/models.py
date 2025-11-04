from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from db import Base


class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"
    id = Column(Integer, primary_key=True)
    key = Column(String(255), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, nullable=False)

    versions = relationship("KnowledgeVersion", back_populates="item", cascade="all, delete-orphan")


class KnowledgeVersion(Base):
    __tablename__ = "knowledge_versions"
    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("knowledge_items.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    author = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, index=True)

    item = relationship("KnowledgeItem", back_populates="versions")

    __table_args__ = (
        UniqueConstraint("item_id", "version_number", name="uix_item_version"),
        Index("idx_item_created_at", "item_id", "created_at"),
    )

