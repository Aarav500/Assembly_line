from datetime import datetime
from .extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    posts = db.relationship(
        "Post",
        back_populates="author",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"


class Post(db.Model):
    __tablename__ = "posts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    published = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    author = db.relationship("User", back_populates="posts")

    __table_args__ = (
        db.UniqueConstraint("user_id", "title", name="uq_user_title"),
        db.Index("ix_posts_published_created_at", "published", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Post id={self.id} user_id={self.user_id} title={self.title!r}>"

