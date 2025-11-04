import json
from datetime import datetime
from sqlalchemy.orm import declarative_base, relationship, Mapped, mapped_column
from sqlalchemy import Integer, String, DateTime, ForeignKey, Text, UniqueConstraint, Index

Base = declarative_base()


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    root_path: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    files: Mapped[list["CodeFile"]] = relationship("CodeFile", back_populates="project", cascade="all, delete-orphan")
    functions: Mapped[list["Function"]] = relationship("Function", back_populates="project", cascade="all, delete-orphan")
    imports: Mapped[list["ImportUsage"]] = relationship("ImportUsage", back_populates="project", cascade="all, delete-orphan")
    requirements: Mapped[list["Requirement"]] = relationship("Requirement", back_populates="project", cascade="all, delete-orphan")


class CodeFile(Base):
    __tablename__ = "code_files"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    rel_path: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    language: Mapped[str] = mapped_column(String(32), default="python")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)

    project: Mapped[Project] = relationship("Project", back_populates="files")
    functions: Mapped[list["Function"]] = relationship("Function", back_populates="file", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("project_id", "rel_path", name="uq_file_per_project"),
        Index("ix_file_project_sha", "project_id", "sha256"),
    )


class Function(Base):
    __tablename__ = "functions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    file_id: Mapped[int] = mapped_column(Integer, ForeignKey("code_files.id", ondelete="CASCADE"), index=True)

    qualname: Mapped[str] = mapped_column(Text, nullable=False)  # module.Class.func or module.func
    name: Mapped[str] = mapped_column(String(255), index=True)
    args_signature: Mapped[str] = mapped_column(Text, default="")
    docstring: Mapped[str | None] = mapped_column(Text, nullable=True)

    start_line: Mapped[int] = mapped_column(Integer, default=0)
    end_line: Mapped[int] = mapped_column(Integer, default=0)

    ast_types_seq: Mapped[str] = mapped_column(Text, default="")  # JSON list of node type names
    ast_norm_hash: Mapped[str] = mapped_column(String(64), index=True)  # hash of normalized AST structure
    token_shingles: Mapped[str] = mapped_column(Text, default="[]")  # JSON list of shingles strings

    project: Mapped[Project] = relationship("Project", back_populates="functions")
    file: Mapped[CodeFile] = relationship("CodeFile", back_populates="functions")

    __table_args__ = (
        Index("ix_func_proj_name", "project_id", "name"),
        Index("ix_func_ast_hash", "ast_norm_hash"),
    )

    def shingles(self) -> set[str]:
        try:
            return set(json.loads(self.token_shingles))
        except Exception:
            return set()

    def ast_types(self) -> list[str]:
        try:
            return list(json.loads(self.ast_types_seq))
        except Exception:
            return []


class ImportUsage(Base):
    __tablename__ = "import_usage"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    file_id: Mapped[int] = mapped_column(Integer, ForeignKey("code_files.id", ondelete="CASCADE"), index=True)
    module: Mapped[str] = mapped_column(String(255), index=True)

    project: Mapped[Project] = relationship("Project", back_populates="imports")
    file: Mapped[CodeFile] = relationship("CodeFile")

    __table_args__ = (
        Index("ix_import_proj_mod", "project_id", "module"),
    )


class Requirement(Base):
    __tablename__ = "requirements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    spec: Mapped[str] = mapped_column(String(255), default="")

    project: Mapped[Project] = relationship("Project", back_populates="requirements")

    __table_args__ = (
        Index("ix_req_proj_name", "project_id", "name"),
    )

