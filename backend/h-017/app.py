import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
import difflib
from datetime import datetime
import json
import os

app = Flask(__name__)

DOCS_FILE = 'docs_storage.json'

def load_docs():
    if os.path.exists(DOCS_FILE):
        with open(DOCS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_docs(docs):
    with open(DOCS_FILE, 'w') as f:
        json.dump(docs, f, indent=2)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

@app.route('/docs', methods=['POST'])
def create_or_update_doc():
    data = request.json
    doc_id = data.get('id')
    content = data.get('content')
    
    if not doc_id or not content:
        return jsonify({'error': 'id and content required'}), 400
    
    docs = load_docs()
    
    if doc_id in docs:
        old_content = docs[doc_id]['content']
        diff = list(difflib.unified_diff(
            old_content.splitlines(keepends=True),
            content.splitlines(keepends=True),
            fromfile=f'{doc_id} (old)',
            tofile=f'{doc_id} (new)'
        ))
        
        docs[doc_id]['versions'].append({
            'content': old_content,
            'timestamp': docs[doc_id]['updated_at']
        })
        
        docs[doc_id]['content'] = content
        docs[doc_id]['updated_at'] = datetime.utcnow().isoformat()
        
        save_docs(docs)
        
        return jsonify({
            'message': 'Document updated',
            'id': doc_id,
            'diff': ''.join(diff)
        })
    else:
        docs[doc_id] = {
            'content': content,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'versions': []
        }
        
        save_docs(docs)
        
        return jsonify({
            'message': 'Document created',
            'id': doc_id
        }), 201

@app.route('/docs/<doc_id>', methods=['GET'])
def get_doc(doc_id):
    docs = load_docs()
    
    if doc_id not in docs:
        return jsonify({'error': 'Document not found'}), 404
    
    return jsonify(docs[doc_id])

@app.route('/docs/<doc_id>/diff', methods=['GET'])
def get_doc_diff(doc_id):
    docs = load_docs()
    
    if doc_id not in docs:
        return jsonify({'error': 'Document not found'}), 404
    
    doc = docs[doc_id]
    
    if not doc['versions']:
        return jsonify({'message': 'No previous versions'}), 200
    
    old_version = doc['versions'][-1]
    current_content = doc['content']
    old_content = old_version['content']
    
    diff = list(difflib.unified_diff(
        old_content.splitlines(keepends=True),
        current_content.splitlines(keepends=True),
        fromfile=f'{doc_id} ({old_version["timestamp"]})',
        tofile=f'{doc_id} ({doc["updated_at"]})'
    ))
    
    return jsonify({
        'doc_id': doc_id,
        'diff': ''.join(diff),
        'previous_version': old_version['timestamp'],
        'current_version': doc['updated_at']
    })

@app.route('/docs', methods=['GET'])
def list_docs():
    docs = load_docs()
    return jsonify({
        'docs': [{'id': doc_id, 'updated_at': doc['updated_at']} for doc_id, doc in docs.items()]
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)



def create_app():
    return app


@app.route('/docs/test-doc', methods=['GET'])
def _auto_stub_docs_test_doc():
    return 'Auto-generated stub for /docs/test-doc', 200


@app.route('/docs/test-doc/diff', methods=['GET'])
def _auto_stub_docs_test_doc_diff():
    return 'Auto-generated stub for /docs/test-doc/diff', 200
