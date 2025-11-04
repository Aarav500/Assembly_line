import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import threading
import time

app = Flask(__name__)

ideas = {}
idea_counter = 0
archival_policies = {}

DEFAULT_EXPIRATION_DAYS = 30

def auto_purge_worker():
    while True:
        time.sleep(60)
        now = datetime.now()
        expired_ideas = []
        for idea_id, idea in ideas.items():
            if idea.get('expiration_date') and datetime.fromisoformat(idea['expiration_date']) <= now:
                if idea.get('auto_purge', False):
                    expired_ideas.append(idea_id)
        for idea_id in expired_ideas:
            del ideas[idea_id]

purge_thread = threading.Thread(target=auto_purge_worker, daemon=True)
purge_thread.start()

@app.route('/ideas', methods=['GET'])
def get_ideas():
    return jsonify(list(ideas.values()))

@app.route('/ideas', methods=['POST'])
def create_idea():
    global idea_counter
    data = request.get_json()
    
    if not data or 'title' not in data:
        return jsonify({'error': 'Title is required'}), 400
    
    idea_counter += 1
    idea_id = idea_counter
    
    expiration_days = data.get('expiration_days', DEFAULT_EXPIRATION_DAYS)
    expiration_date = (datetime.now() + timedelta(days=expiration_days)).isoformat()
    
    idea = {
        'id': idea_id,
        'title': data['title'],
        'description': data.get('description', ''),
        'created_at': datetime.now().isoformat(),
        'expiration_date': expiration_date,
        'auto_purge': data.get('auto_purge', False),
        'archived': False
    }
    
    ideas[idea_id] = idea
    return jsonify(idea), 201

@app.route('/ideas/<int:idea_id>/archive', methods=['POST'])
def archive_idea(idea_id):
    if idea_id not in ideas:
        return jsonify({'error': 'Idea not found'}), 404
    
    ideas[idea_id]['archived'] = True
    ideas[idea_id]['archived_at'] = datetime.now().isoformat()
    return jsonify(ideas[idea_id])

@app.route('/ideas/<int:idea_id>', methods=['DELETE'])
def delete_idea(idea_id):
    if idea_id not in ideas:
        return jsonify({'error': 'Idea not found'}), 404
    
    del ideas[idea_id]
    return '', 204

@app.route('/policies', methods=['POST'])
def create_policy():
    data = request.get_json()
    
    if not data or 'name' not in data:
        return jsonify({'error': 'Policy name is required'}), 400
    
    policy = {
        'name': data['name'],
        'expiration_days': data.get('expiration_days', DEFAULT_EXPIRATION_DAYS),
        'auto_purge': data.get('auto_purge', False),
        'archive_before_purge': data.get('archive_before_purge', True)
    }
    
    archival_policies[data['name']] = policy
    return jsonify(policy), 201

@app.route('/policies', methods=['GET'])
def get_policies():
    return jsonify(list(archival_policies.values()))

if __name__ == '__main__':
    app.run(debug=True)


def create_app():
    return app
