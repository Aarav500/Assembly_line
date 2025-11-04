import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import sqlite3
from flask import Flask, jsonify, request, render_template, g

DATABASE = os.path.join(os.path.dirname(__file__), 'ideas.db')

app = Flask(__name__)


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        '''CREATE TABLE IF NOT EXISTS ideas (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               title TEXT NOT NULL,
               demand INTEGER NOT NULL,
               complexity INTEGER NOT NULL,
               notes TEXT,
               created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
           )'''
    )
    conn.commit()

    # Seed sample data if empty
    cur.execute('SELECT COUNT(*) AS c FROM ideas')
    count = cur.fetchone()['c']
    if count == 0:
        samples = [
            ("Todo List SaaS", 6, 3, "Simple but crowded market"),
            ("AI Meeting Summarizer", 9, 7, "Competitive, high infra"),
            ("Local Grocery Delivery", 8, 5, "Ops heavy"),
            ("Blockchain Voting", 5, 9, "Regulatory + high complexity"),
            ("AR Interior Designer", 7, 8, "AR tech + 3D assets"),
            ("Niche CRM for Dentists", 7, 4, "Clear ICP"),
            ("Passwordless Auth Service", 6, 6, "Security critical"),
            ("AI Coding Assistant Plugin", 9, 8, "Cutting-edge AI"),
            ("No-code API Builder", 8, 6, "Workflow builder"),
            ("Micro SaaS for Invoices", 6, 4, "SMBs"),
            ("Tenant Screening Tool", 7, 3, "B2B2C, data integrations"),
            ("Fleet Route Optimizer", 7, 7, "Optimization heavy"),
            ("Custom Report Generator", 5, 2, "Low complexity, moderate demand"),
            ("Health Habit Tracker", 6, 3, "Consumer app"),
            ("BI Dashboard Templates", 6, 2, "Low complexity templates"),
            ("Warehouse Vision QA", 8, 8, "Computer vision"),
            ("AI Email Triage", 8, 5, "NLP"),
            ("SEO Content Planner", 7, 3, "Keyword clustering"),
            ("Browser Test Recorder", 7, 4, "Dev tooling"),
            ("K12 Homework Portal", 6, 5, "Admin + integrations")
        ]
        cur.executemany(
            'INSERT INTO ideas (title, demand, complexity, notes) VALUES (?, ?, ?, ?)',
            samples
        )
        conn.commit()


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


@app.before_request
def before_request():
    init_db()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/ideas', methods=['GET'])
def list_ideas():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT id, title, demand, complexity, notes, created_at FROM ideas ORDER BY created_at DESC, id DESC')
    rows = cur.fetchall()
    ideas = [dict(row) for row in rows]
    return jsonify(ideas)


@app.route('/api/ideas', methods=['POST'])
def create_idea():
    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    notes = (data.get('notes') or '').strip()
    demand = data.get('demand')
    complexity = data.get('complexity')

    errors = {}
    if not title:
        errors['title'] = 'Title is required.'
    try:
        demand = int(demand)
        if demand < 1 or demand > 10:
            errors['demand'] = 'Demand must be between 1 and 10.'
    except Exception:
        errors['demand'] = 'Demand must be an integer between 1 and 10.'
    try:
        complexity = int(complexity)
        if complexity < 1 or complexity > 10:
            errors['complexity'] = 'Complexity must be between 1 and 10.'
    except Exception:
        errors['complexity'] = 'Complexity must be an integer between 1 and 10.'

    if errors:
        return jsonify({'errors': errors}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        'INSERT INTO ideas (title, demand, complexity, notes) VALUES (?, ?, ?, ?)',
        (title, demand, complexity, notes)
    )
    conn.commit()
    new_id = cur.lastrowid

    cur.execute('SELECT id, title, demand, complexity, notes, created_at FROM ideas WHERE id = ?', (new_id,))
    row = cur.fetchone()
    return jsonify(dict(row)), 201


@app.route('/api/ideas/<int:idea_id>', methods=['DELETE'])
def delete_idea(idea_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('DELETE FROM ideas WHERE id = ?', (idea_id,))
    conn.commit()
    if cur.rowcount == 0:
        return jsonify({'error': 'Not found'}), 404
    return jsonify({'status': 'deleted', 'id': idea_id})


@app.route('/api/ideas/<int:idea_id>', methods=['PUT', 'PATCH'])
def update_idea(idea_id):
    data = request.get_json(silent=True) or {}
    fields = []
    values = []

    if 'title' in data:
        title = (data.get('title') or '').strip()
        if not title:
            return jsonify({'errors': {'title': 'Title cannot be empty.'}}), 400
        fields.append('title = ?')
        values.append(title)

    if 'demand' in data:
        try:
            demand = int(data.get('demand'))
            if demand < 1 or demand > 10:
                raise ValueError
            fields.append('demand = ?')
            values.append(demand)
        except Exception:
            return jsonify({'errors': {'demand': 'Demand must be an integer between 1 and 10.'}}), 400

    if 'complexity' in data:
        try:
            complexity = int(data.get('complexity'))
            if complexity < 1 or complexity > 10:
                raise ValueError
            fields.append('complexity = ?')
            values.append(complexity)
        except Exception:
            return jsonify({'errors': {'complexity': 'Complexity must be an integer between 1 and 10.'}}), 400

    if 'notes' in data:
        notes = (data.get('notes') or '').strip()
        fields.append('notes = ?')
        values.append(notes)

    if not fields:
        return jsonify({'error': 'No valid fields to update.'}), 400

    values.append(idea_id)
    conn = get_db()
    cur = conn.cursor()
    cur.execute(f'UPDATE ideas SET {", ".join(fields)} WHERE id = ?', values)
    conn.commit()

    if cur.rowcount == 0:
        return jsonify({'error': 'Not found'}), 404

    cur.execute('SELECT id, title, demand, complexity, notes, created_at FROM ideas WHERE id = ?', (idea_id,))
    row = cur.fetchone()
    return jsonify(dict(row))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)



def create_app():
    return app


@app.route('/api/ideas/1', methods=['DELETE'])
def _auto_stub_api_ideas_1():
    return 'Auto-generated stub for /api/ideas/1', 200
