import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from datetime import datetime
from models import db, User, Board, Idea, Vote, Comment
from functools import wraps


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()

    @app.context_processor
    def inject_user():
        user = None
        if 'user_id' in session:
            user = User.query.get(session['user_id'])
        return dict(current_user=user)

    def login_required(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please sign in to continue.', 'warning')
                return redirect(url_for('login', next=request.path))
            return f(*args, **kwargs)
        return wrapper

    @app.route('/')
    def index():
        boards = Board.query.order_by(Board.created_at.desc()).all()
        return render_template('boards.html', boards=boards)

    @app.route('/boards/new', methods=['POST'])
    @login_required
    def create_board():
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        if not title:
            flash('Board title is required.', 'danger')
            return redirect(url_for('index'))
        board = Board(title=title, description=description, created_by=session['user_id'])
        db.session.add(board)
        db.session.commit()
        flash('Board created.', 'success')
        return redirect(url_for('board_detail', board_id=board.id))

    @app.route('/boards/<int:board_id>')
    def board_detail(board_id):
        board = Board.query.get_or_404(board_id)
        ideas = Idea.query.filter_by(board_id=board.id).order_by(Idea.created_at.desc()).all()
        return render_template('board_detail.html', board=board, ideas=ideas)

    @app.route('/boards/<int:board_id>/ideas/new', methods=['POST'])
    @login_required
    def create_idea(board_id):
        board = Board.query.get_or_404(board_id)
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        if not title:
            flash('Idea title is required.', 'danger')
            return redirect(url_for('board_detail', board_id=board.id))
        idea = Idea(board_id=board.id, title=title, description=description, created_by=session['user_id'])
        db.session.add(idea)
        db.session.commit()
        flash('Idea created.', 'success')
        return redirect(url_for('idea_detail', idea_id=idea.id))

    @app.route('/ideas/<int:idea_id>')
    def idea_detail(idea_id):
        idea = Idea.query.get_or_404(idea_id)
        # Order root comments by created_at
        root_comments = Comment.query.filter_by(idea_id=idea.id, parent_id=None).order_by(Comment.created_at.asc()).all()
        user_vote = None
        if 'user_id' in session:
            user_vote = Vote.query.filter_by(idea_id=idea.id, user_id=session['user_id']).first()
        return render_template('idea_detail.html', idea=idea, root_comments=root_comments, user_vote=user_vote)

    @app.route('/ideas/<int:idea_id>/vote', methods=['POST'])
    @login_required
    def vote(idea_id):
        idea = Idea.query.get_or_404(idea_id)
        action = request.form.get('value')
        if action not in ['up', 'down']:
            abort(400, description='Invalid vote value')
        val = 1 if action == 'up' else -1
        vote = Vote.query.filter_by(idea_id=idea.id, user_id=session['user_id']).first()
        if vote:
            if vote.value == val:
                # toggle off
                db.session.delete(vote)
                db.session.commit()
                flash('Your vote was removed.', 'info')
            else:
                vote.value = val
                db.session.commit()
                flash('Your vote was updated.', 'success')
        else:
            vote = Vote(idea_id=idea.id, user_id=session['user_id'], value=val)
            db.session.add(vote)
            db.session.commit()
            flash('Your vote was recorded.', 'success')
        return redirect(url_for('idea_detail', idea_id=idea.id))

    @app.route('/ideas/<int:idea_id>/comments', methods=['POST'])
    @login_required
    def add_comment(idea_id):
        idea = Idea.query.get_or_404(idea_id)
        content = request.form.get('content', '').strip()
        parent_id = request.form.get('parent_id')
        parent = None
        if parent_id:
            parent = Comment.query.filter_by(id=parent_id, idea_id=idea.id).first()
            if not parent:
                abort(400, description='Invalid parent comment')
        if not content:
            flash('Comment cannot be empty.', 'danger')
            return redirect(url_for('idea_detail', idea_id=idea.id))
        comment = Comment(idea_id=idea.id, user_id=session['user_id'], content=content, parent_id=parent.id if parent else None)
        db.session.add(comment)
        db.session.commit()
        flash('Comment posted.', 'success')
        return redirect(url_for('idea_detail', idea_id=idea.id))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            if not username:
                flash('Username is required.', 'danger')
                return redirect(url_for('login'))
            user = User.query.filter(db.func.lower(User.username) == username.lower()).first()
            if not user:
                user = User(username=username)
                db.session.add(user)
                db.session.commit()
            session['user_id'] = user.id
            session['username'] = user.username
            flash(f'Signed in as {user.username}', 'success')
            next_url = request.args.get('next')
            return redirect(next_url or url_for('index'))
        return render_template('login.html')

    @app.route('/logout')
    def logout():
        session.clear()
        flash('Signed out.', 'info')
        return redirect(url_for('index'))

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)

