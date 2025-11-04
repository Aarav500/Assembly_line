from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import User, Post


def create_user(session: Session, *, email: str, name: str) -> User:
    user = User(email=email, name=name)
    session.add(user)
    session.flush()
    return user


def get_user_by_email(session: Session, *, email: str) -> Optional[User]:
    stmt = select(User).where(User.email == email)
    return session.execute(stmt).scalars().first()


def create_post(session: Session, *, user_id: int, title: str, body: Optional[str] = None) -> Post:
    post = Post(user_id=user_id, title=title, body=body)
    session.add(post)
    session.flush()
    return post


def get_user_posts(session: Session, *, user_id: int) -> Sequence[Post]:
    stmt = select(Post).where(Post.user_id == user_id).order_by(Post.id.asc())
    return list(session.execute(stmt).scalars().all())

