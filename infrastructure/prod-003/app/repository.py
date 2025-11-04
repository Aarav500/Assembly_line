from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import User


def get_user_by_id(session: Session, user_id: int) -> Optional[User]:
    return session.get(User, user_id)


def list_users(session: Session, limit: int = 10) -> Iterable[User]:
    stmt = select(User).limit(limit)
    return session.scalars(stmt).all()


def create_user(session: Session, name: str, email: Optional[str] = None) -> User:
    user = User(name=name, email=email)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

