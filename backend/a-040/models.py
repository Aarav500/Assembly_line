from datetime import datetime
from extensions import db

project_tags = db.Table(
    "project_tags",
    db.Column("project_id", db.Integer, db.ForeignKey("project.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tag.id"), primary_key=True),
)

idea_tags = db.Table(
    "idea_tags",
    db.Column("idea_id", db.Integer, db.ForeignKey("idea.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tag.id"), primary_key=True),
)


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Tag(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False, index=True)

    @staticmethod
    def ensure(name: str):
        name = (name or '').strip().lower()
        existing = Tag.query.filter_by(name=name).first()
        if existing:
            return existing
        t = Tag(name=name)
        db.session.add(t)
        return t


class Project(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(32), default="active")

    features = db.relationship("ProjectFeature", backref="project", cascade="all, delete-orphan", lazy=True)
    tags = db.relationship("Tag", secondary=project_tags, backref=db.backref("projects", lazy=True))


class ProjectFeature(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    priority = db.Column(db.String(16), default="Medium")  # High, Medium, Low


class Idea(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    summary = db.Column(db.Text)
    problem = db.Column(db.Text)
    solution = db.Column(db.Text)
    status = db.Column(db.String(32), default="draft")

    source_project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=True, index=True)
    source_project = db.relationship("Project", backref=db.backref("converted_ideas", lazy=True))

    features = db.relationship("IdeaFeature", backref="idea", cascade="all, delete-orphan", lazy=True)
    tags = db.relationship("Tag", secondary=idea_tags, backref=db.backref("ideas", lazy=True))


class IdeaFeature(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    idea_id = db.Column(db.Integer, db.ForeignKey("idea.id"), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    impact = db.Column(db.String(16), default="Medium")  # High, Medium, Low

