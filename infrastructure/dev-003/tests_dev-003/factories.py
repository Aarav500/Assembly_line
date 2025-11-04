from itertools import count
from typing import Iterable, List, Optional
from sqlalchemy.orm import Session
from app.models import User, Post

_email_seq = count(1)
_title_seq = count(1)


def make_user(session: Session, *, email: Optional[str] = None, name: Optional[str] = None) -> User:
    email = email or f"user{next(_email_seq)}@example.com"
    name = name or "Test User"
    user = User(email=email, name=name)
    session.add(user)
    session.flush()
    return user


def make_users(session: Session, *, count_: int = 1) -> List[User]:
    users: List[User] = []
    for _ in range(count_):
        users.append(make_user(session))
    return users


def make_post(
    session: Session,
    *,
    user: Optional[User] = None,
    user_id: Optional[int] = None,
    title: Optional[str] = None,
    body: Optional[str] = None,
) -> Post:
    if user is None and user_id is None:
        user = make_user(session)
    if user_id is None:
        assert user is not None
        user_id = user.id
    title = title or f"Post {next(_title_seq)}"
    post = Post(user_id=user_id, title=title, body=body)
    session.add(post)
    session.flush()
    return post


def make_posts(session: Session, *, user: Optional[User] = None, user_id: Optional[int] = None, count_: int = 1) -> List[Post]:
    posts: List[Post] = []
    for _ in range(count_):
        posts.append(make_post(session, user=user, user_id=user_id))
    return posts

