from flask_sqlalchemy import SQLAlchemy
from datetime import datetime


db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<User {self.username}>'


class Board(db.Model):
    __tablename__ = 'board'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    creator = db.relationship('User', backref=db.backref('boards', lazy=True))

    def __repr__(self):
        return f'<Board {self.title}>'


class Idea(db.Model):
    __tablename__ = 'idea'
    id = db.Column(db.Integer, primary_key=True)
    board_id = db.Column(db.Integer, db.ForeignKey('board.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    board = db.relationship('Board', backref=db.backref('ideas', lazy=True, cascade='all, delete-orphan'))
    creator = db.relationship('User', backref=db.backref('ideas', lazy=True))

    votes = db.relationship('Vote', backref='idea', lazy=True, cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='idea', lazy=True, cascade='all, delete-orphan')

    @property
    def score(self):
        return sum(v.value for v in self.votes)

    def __repr__(self):
        return f'<Idea {self.title}>'


class Vote(db.Model):
    __tablename__ = 'vote'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    idea_id = db.Column(db.Integer, db.ForeignKey('idea.id'), nullable=False)
    value = db.Column(db.Integer, nullable=False)  # 1 or -1
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref=db.backref('votes', lazy=True))

    __table_args__ = (
        db.UniqueConstraint('user_id', 'idea_id', name='uq_vote_user_idea'),
    )

    def __repr__(self):
        return f'<Vote user={self.user_id} idea={self.idea_id} value={self.value}>'


class Comment(db.Model):
    __tablename__ = 'comment'
    id = db.Column(db.Integer, primary_key=True)
    idea_id = db.Column(db.Integer, db.ForeignKey('idea.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref=db.backref('comments', lazy=True))
    # self-referential relationship
    children = db.relationship(
        'Comment',
        backref=db.backref('parent', remote_side=[id]),
        lazy=True,
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f'<Comment {self.id} by {self.user_id}>'

