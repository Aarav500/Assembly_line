from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    UniqueConstraint,
    ForeignKey,
    Text,
)
from sqlalchemy.sql import func

Base = declarative_base()

class Artifact(Base):
    __tablename__ = "artifacts"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    hash = Column(String(64), nullable=False, index=True)  # sha256 hex
    size = Column(Integer, nullable=False)
    content_type = Column(String(255), nullable=True)
    filename = Column(String(512), nullable=True)
    path = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    tags = relationship("ArtifactTag", back_populates="artifact", cascade="all,delete", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("name", "hash", name="uix_artifact_name_hash"),
    )

class ArtifactTag(Base):
    __tablename__ = "artifact_tags"
    id = Column(Integer, primary_key=True)
    artifact_id = Column(Integer, ForeignKey("artifacts.id", ondelete="CASCADE"), nullable=False, index=True)
    artifact_name = Column(String(255), nullable=False, index=True)
    tag = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    artifact = relationship("Artifact", back_populates="tags")

    __table_args__ = (
        UniqueConstraint("artifact_name", "tag", name="uix_artifact_tag_unique"),
    )

class Module(Base):
    __tablename__ = "modules"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    version = Column(String(128), nullable=False, index=True)
    size = Column(Integer, nullable=False)
    content_type = Column(String(255), nullable=True)
    filename = Column(String(512), nullable=True)
    path = Column(Text, nullable=False)
    sha256 = Column(String(64), nullable=False)

    semver_major = Column(Integer, nullable=False)
    semver_minor = Column(Integer, nullable=False)
    semver_patch = Column(Integer, nullable=False)
    semver_prerelease = Column(String(128), nullable=True)
    semver_build = Column(String(128), nullable=True)

    metadata = Column(Text, nullable=True)  # json string if provided

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("name", "version", name="uix_module_name_version"),
    )

