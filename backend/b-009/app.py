import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from datetime import datetime
from flask import Flask, jsonify, request, render_template, redirect, url_for, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from services.swot import generate_swot

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'swot.db')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + DB_PATH
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

OPENAI_ENABLED = bool(os.environ.get('OPENAI_API_KEY'))
DEFAULT_PROVIDER = os.environ.get('SWOT_PROVIDER', 'rule')  # 'rule' or 'openai'


db = SQLAlchemy(app)


class Idea(db.Model):
    __tablename__ = 'ideas'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    swot = db.relationship('Swot', backref='idea', uselist=False, cascade='all, delete-orphan')


class Swot(db.Model):
    __tablename__ = 'swots'
    id = db.Column(db.Integer, primary_key=True)
    idea_id = db.Column(db.Integer, db.ForeignKey('ideas.id'), nullable=False, unique=True)
    strengths = db.Column(db.Text, nullable=False)
    weaknesses = db.Column(db.Text, nullable=False)
    opportunities = db.Column(db.Text, nullable=False)
    threats = db.Column(db.Text, nullable=False)
    provider = db.Column(db.String(50), nullable=False, default='rule')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


with app.app_context():
    db.create_all()


def serialize_swot(swot: Swot):
    return {
        'id': swot.id,
        'idea_id': swot.idea_id,
        'strengths': swot.strengths.split('\n'),
        'weaknesses': swot.weaknesses.split('\n'),
        'opportunities': swot.opportunities.split('\n'),
        'threats': swot.threats.split('\n'),
        'provider': swot.provider,
        'created_at': swot.created_at.isoformat(),
    }


def serialize_idea(idea: Idea, include_swot=True):
    data = {
        'id': idea.id,
        'title': idea.title,
        'description': idea.description,
        'created_at': idea.created_at.isoformat(),
    }
    if include_swot and idea.swot:
        data['swot'] = serialize_swot(idea.swot)
    return data


@app.route('/')
def index():
    return render_template('index.html', openai_enabled=OPENAI_ENABLED)


@app.route('/idea/<int:idea_id>')
def view_idea(idea_id):
    idea = db.session.get(Idea, idea_id)
    if not idea:
        abort(404)
    return render_template('index.html', openai_enabled=OPENAI_ENABLED, initial_idea=serialize_idea(idea))


@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify({
        'openai_enabled': OPENAI_ENABLED,
        'default_provider': DEFAULT_PROVIDER,
    })


@app.route('/api/ideas', methods=['GET'])
def list_ideas():
    q = Idea.query.order_by(Idea.created_at.desc()).limit(50)
    return jsonify([serialize_idea(i, include_swot=False) for i in q.all()])


@app.route('/api/ideas/<int:idea_id>', methods=['GET'])
def get_idea(idea_id):
    idea = db.session.get(Idea, idea_id)
    if not idea:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(serialize_idea(idea))


@app.route('/api/ideas', methods=['POST'])
def create_idea():
    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    description = (data.get('description') or '').strip()
    provider = (data.get('provider') or DEFAULT_PROVIDER).strip()

    if not title or not description:
        return jsonify({'error': 'title and description are required'}), 400

    idea = Idea(title=title, description=description)
    db.session.add(idea)
    db.session.flush()  # get idea.id

    try:
        swot = generate_swot(title=title, description=description, provider=provider)
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to generate SWOT: {str(e)}'}), 500

    swot_row = Swot(
        idea_id=idea.id,
        strengths='\n'.join(swot['strengths']),
        weaknesses='\n'.join(swot['weaknesses']),
        opportunities='\n'.join(swot['opportunities']),
        threats='\n'.join(swot['threats']),
        provider=swot.get('provider') or provider,
    )
    db.session.add(swot_row)
    db.session.commit()
    return jsonify(serialize_idea(idea)), 201


@app.route('/api/ideas/<int:idea_id>/regenerate', methods=['POST'])
def regenerate_swot(idea_id):
    idea = db.session.get(Idea, idea_id)
    if not idea:
        return jsonify({'error': 'Not found'}), 404

    data = request.get_json(silent=True) or {}
    provider = (data.get('provider') or DEFAULT_PROVIDER).strip()

    try:
        swot = generate_swot(title=idea.title, description=idea.description, provider=provider)
    except Exception as e:
        return jsonify({'error': f'Failed to generate SWOT: {str(e)}'}), 500

    if idea.swot:
        idea.swot.strengths = '\n'.join(swot['strengths'])
        idea.swot.weaknesses = '\n'.join(swot['weaknesses'])
        idea.swot.opportunities = '\n'.join(swot['opportunities'])
        idea.swot.threats = '\n'.join(swot['threats'])
        idea.swot.provider = swot.get('provider') or provider
        idea.swot.created_at = datetime.utcnow()
    else:
        swot_row = Swot(
            idea_id=idea.id,
            strengths='\n'.join(swot['strengths']),
            weaknesses='\n'.join(swot['weaknesses']),
            opportunities='\n'.join(swot['opportunities']),
            threats='\n'.join(swot['threats']),
            provider=swot.get('provider') or provider,
        )
        db.session.add(swot_row)

    db.session.commit()
    return jsonify(serialize_idea(idea))


@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Not found'}), 404
    return render_template('404.html'), 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)



def create_app():
    return app


@app.route('/analyze', methods=['POST'])
def _auto_stub_analyze():
    return 'Auto-generated stub for /analyze', 200
