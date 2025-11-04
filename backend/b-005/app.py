import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
import difflib

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ideas.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class Idea(db.Model):
    __tablename__ = 'ideas'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('ideas.id'), nullable=True)
    base_revision_id = db.Column(db.Integer, db.ForeignKey('revisions.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    parent = db.relationship('Idea', remote_side=[id], backref=db.backref('forks', lazy='dynamic'))
    base_revision = db.relationship('Revision', foreign_keys=[base_revision_id])
    revisions = db.relationship('Revision', backref='idea', order_by='Revision.version', lazy='dynamic')

    def latest_revision(self):
        return self.revisions.order_by(Revision.version.desc()).first()


class Revision(db.Model):
    __tablename__ = 'revisions'
    id = db.Column(db.Integer, primary_key=True)
    idea_id = db.Column(db.Integer, db.ForeignKey('ideas.id'), nullable=False)
    version = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)
    message = db.Column(db.String(500), nullable=False, default='')
    parent_revision_id = db.Column(db.Integer, db.ForeignKey('revisions.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    parent_revision = db.relationship('Revision', remote_side=[id])


class MergeRequest(db.Model):
    __tablename__ = 'merge_requests'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    source_idea_id = db.Column(db.Integer, db.ForeignKey('ideas.id'), nullable=False)
    target_idea_id = db.Column(db.Integer, db.ForeignKey('ideas.id'), nullable=False)
    base_revision_id = db.Column(db.Integer, db.ForeignKey('revisions.id'), nullable=True)
    status = db.Column(db.String(20), default='open')  # open, merged, closed
    merged_revision_id = db.Column(db.Integer, db.ForeignKey('revisions.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    closed_at = db.Column(db.DateTime, nullable=True)

    source_idea = db.relationship('Idea', foreign_keys=[source_idea_id])
    target_idea = db.relationship('Idea', foreign_keys=[target_idea_id])
    base_revision = db.relationship('Revision', foreign_keys=[base_revision_id])
    merged_revision = db.relationship('Revision', foreign_keys=[merged_revision_id])


def init_db():
    with app.app_context():
        db.create_all()


@app.context_processor
def inject_now():
    return {'now': datetime.utcnow}


def create_revision(idea: Idea, content: str, message: str, parent_revision: Revision | None = None) -> Revision:
    prev = idea.latest_revision()
    version = 1 if prev is None else (prev.version + 1)
    rev = Revision(
        idea_id=idea.id,
        version=version,
        content=content,
        message=message or f"Update to v{version}",
        parent_revision_id=prev.id if prev else None,
    )
    db.session.add(rev)
    idea.content = content
    db.session.commit()
    return rev


def unified_diff(a_text: str, b_text: str, from_label: str = 'from', to_label: str = 'to'):
    a_lines = a_text.splitlines(keepends=True)
    b_lines = b_text.splitlines(keepends=True)
    diff = list(difflib.unified_diff(a_lines, b_lines, fromfile=from_label, tofile=to_label, lineterm=''))
    return diff


def simple_three_way_merge(base: str, target: str, source: str) -> tuple[str, bool]:
    """
    Very conservative 3-way merge.
    - If target unchanged since base: take source (fast-forward target).
    - If source unchanged since base: keep target.
    - If both changed and equal: take either.
    - Else: produce conflict markers including base for context.
    Returns (merged_text, has_conflicts)
    """
    if target == base and source != base:
        return source, False
    if source == base and target != base:
        return target, False
    if source == target:
        return target, False
    conflict = []
    conflict.append('<<<<<<< TARGET\n')
    conflict.append(target if target.endswith('\n') else target + '\n')
    conflict.append('||||||| BASE\n')
    conflict.append(base if base.endswith('\n') else base + '\n')
    conflict.append('=======\n')
    conflict.append(source if source.endswith('\n') else source + '\n')
    conflict.append('>>>>>>> SOURCE\n')
    return ''.join(conflict), True


def guess_base_revision(source: Idea, target: Idea) -> Revision | None:
    # If source is fork of target
    if source.parent_id == target.id:
        return source.base_revision
    # If target is fork of source
    if target.parent_id == source.id:
        return target.base_revision
    # If both forked from same parent, pick the earlier base revision if available
    if source.parent_id is not None and source.parent_id == target.parent_id:
        # Choose the older of the two base revisions if both exist
        if source.base_revision and target.base_revision:
            return source.base_revision if source.base_revision.created_at <= target.base_revision.created_at else target.base_revision
        return source.base_revision or target.base_revision
    # Fallback: use target's latest revision
    return target.latest_revision()


@app.route('/')
def index():
    ideas = Idea.query.order_by(Idea.created_at.desc()).all()
    mrs = MergeRequest.query.order_by(MergeRequest.created_at.desc()).limit(5).all()
    return render_template('index.html', ideas=ideas, mrs=mrs)


@app.route('/ideas/new', methods=['GET', 'POST'])
def new_idea():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '')
        if not title:
            flash('Title is required.', 'error')
            return redirect(url_for('new_idea'))
        idea = Idea(title=title, content=content)
        db.session.add(idea)
        db.session.commit()
        rev = Revision(idea_id=idea.id, version=1, content=content, message='Initial commit')
        db.session.add(rev)
        db.session.commit()
        flash('Idea created.', 'success')
        return redirect(url_for('idea_detail', idea_id=idea.id))
    return render_template('idea_new.html')


@app.route('/ideas/<int:idea_id>')
def idea_detail(idea_id):
    idea = Idea.query.get_or_404(idea_id)
    latest = idea.latest_revision()
    return render_template('idea_detail.html', idea=idea, latest=latest)


@app.route('/ideas/<int:idea_id>/edit', methods=['POST'])
def idea_edit(idea_id):
    idea = Idea.query.get_or_404(idea_id)
    content = request.form.get('content', '')
    message = request.form.get('message', 'Update')
    create_revision(idea, content, message, parent_revision=idea.latest_revision())
    flash('Revision created.', 'success')
    return redirect(url_for('idea_detail', idea_id=idea.id))


@app.route('/ideas/<int:idea_id>/history')
def idea_history(idea_id):
    idea = Idea.query.get_or_404(idea_id)
    revisions = idea.revisions.order_by(Revision.version.desc()).all()
    return render_template('history.html', idea=idea, revisions=revisions)


@app.route('/revisions/<int:rev_a_id>/diff/<int:rev_b_id>')
def revision_diff(rev_a_id, rev_b_id):
    ra = Revision.query.get_or_404(rev_a_id)
    rb = Revision.query.get_or_404(rev_b_id)
    diff_lines = unified_diff(ra.content, rb.content, from_label=f'Idea {ra.idea_id} v{ra.version}', to_label=f'Idea {rb.idea_id} v{rb.version}')
    return render_template('diff.html', diff_lines=diff_lines, a=ra, b=rb)


@app.route('/ideas/<int:idea_id>/fork', methods=['POST'])
def idea_fork(idea_id):
    source = Idea.query.get_or_404(idea_id)
    title = request.form.get('title', '').strip() or f"Fork of {source.title}"
    fork = Idea(title=title, content=source.content, parent_id=source.id, base_revision_id=source.latest_revision().id)
    db.session.add(fork)
    db.session.commit()
    rev = Revision(idea_id=fork.id, version=1, content=fork.content, message=f'Forked from Idea {source.id} rev {source.latest_revision().version}')
    db.session.add(rev)
    db.session.commit()
    flash(f'Fork created: Idea {fork.id}', 'success')
    return redirect(url_for('idea_detail', idea_id=fork.id))


@app.route('/merge_requests')
def merge_requests():
    mrs = MergeRequest.query.order_by(MergeRequest.created_at.desc()).all()
    return render_template('merge_requests.html', mrs=mrs)


@app.route('/merge_requests/new', methods=['GET', 'POST'])
def merge_request_new():
    if request.method == 'POST':
        source_id = request.form.get('source_id', type=int)
        target_id = request.form.get('target_id', type=int)
        title = request.form.get('title', '').strip() or 'Merge Request'
        description = request.form.get('description', '').strip()
        source = Idea.query.get_or_404(source_id)
        target = Idea.query.get_or_404(target_id)
        base_rev = guess_base_revision(source, target)
        mr = MergeRequest(
            title=title,
            description=description,
            source_idea_id=source.id,
            target_idea_id=target.id,
            base_revision_id=base_rev.id if base_rev else None,
            status='open',
        )
        db.session.add(mr)
        db.session.commit()
        flash('Merge Request created.', 'success')
        return redirect(url_for('merge_request_detail', mr_id=mr.id))

    source_id = request.args.get('source', type=int)
    target_id = request.args.get('target', type=int)
    source = Idea.query.get(source_id) if source_id else None
    target = Idea.query.get(target_id) if target_id else None
    return render_template('merge_request_new.html', source=source, target=target)


@app.route('/merge_requests/<int:mr_id>')
def merge_request_detail(mr_id):
    mr = MergeRequest.query.get_or_404(mr_id)
    source_latest = mr.source_idea.latest_revision()
    target_latest = mr.target_idea.latest_revision()
    base_rev = mr.base_revision or mr.target_idea.latest_revision()
    diff_lines = unified_diff(target_latest.content, source_latest.content,
                              from_label=f'Target Idea {mr.target_idea_id} v{target_latest.version}',
                              to_label=f'Source Idea {mr.source_idea_id} v{source_latest.version}')
    return render_template('merge_request_detail.html', mr=mr, diff_lines=diff_lines, base_rev=base_rev,
                           source_latest=source_latest, target_latest=target_latest)


@app.route('/merge_requests/<int:mr_id>/merge', methods=['POST'])
def merge_request_merge(mr_id):
    mr = MergeRequest.query.get_or_404(mr_id)
    if mr.status != 'open':
        flash('Merge Request is not open.', 'error')
        return redirect(url_for('merge_request_detail', mr_id=mr.id))

    base_text = (mr.base_revision.content if mr.base_revision else mr.target_idea.latest_revision().content)
    target_text = mr.target_idea.latest_revision().content
    source_text = mr.source_idea.latest_revision().content

    merged_text, has_conflicts = simple_three_way_merge(base_text, target_text, source_text)
    message = f"Merge MR #{mr.id} from Idea {mr.source_idea_id} into {mr.target_idea_id}"
    if has_conflicts:
        message += ' (with conflicts)'

    new_rev = create_revision(mr.target_idea, merged_text, message)

    mr.status = 'merged'
    mr.merged_revision_id = new_rev.id
    mr.closed_at = datetime.utcnow()
    db.session.commit()

    if has_conflicts:
        flash('Merged with conflicts. Please resolve manually in a new revision.', 'warning')
    else:
        flash('Merged successfully.', 'success')

    return redirect(url_for('idea_detail', idea_id=mr.target_idea_id))


@app.route('/search')
def search():
    q = request.args.get('q', '').strip()
    ideas = []
    if q:
        ideas = Idea.query.filter(Idea.title.ilike(f'%{q}%')).order_by(Idea.created_at.desc()).all()
    return render_template('search.html', q=q, ideas=ideas)


if __name__ == '__main__':
    init_db()
    app.run(debug=True)



def create_app():
    return app
