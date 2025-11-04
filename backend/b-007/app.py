import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import logging
from flask import Flask, request, jsonify, render_template

from embeddings import EmbeddingService
from store import ItemStore

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Initialize services
EMBEDDER = EmbeddingService()
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
os.makedirs(DATA_DIR, exist_ok=True)
STORE = ItemStore(os.path.join(DATA_DIR, 'items.json'))


@app.route('/')
def index():
    return render_template('index.html')


@app.get('/api/items')
def list_items():
    type_filter = request.args.get('type')
    items = STORE.list_items(item_type=type_filter)
    return jsonify({
        'items': items,
        'count': len(items)
    })


@app.post('/api/items')
def add_item():
    data = request.get_json(force=True, silent=True) or {}
    item_type = (data.get('type') or '').strip().lower()
    title = (data.get('title') or '').strip()
    content = (data.get('content') or '').strip()

    if item_type not in {'idea', 'template'}:
        return jsonify({'error': "'type' must be 'idea' or 'template'"}), 400
    if not title:
        return jsonify({'error': "'title' is required"}), 400
    if not content:
        return jsonify({'error': "'content' is required"}), 400

    text = f"{title}\n\n{content}".strip()
    embedding = EMBEDDER.embed(text)
    item = STORE.add_item(item_type=item_type, title=title, content=content, embedding=embedding)
    return jsonify(item), 201


@app.delete('/api/items/<item_id>')
def delete_item(item_id):
    ok = STORE.delete_item(item_id)
    if not ok:
        return jsonify({'error': 'Not found'}), 404
    return jsonify({'deleted': True})


@app.post('/api/search')
def search():
    data = request.get_json(force=True, silent=True) or {}
    query = (data.get('query') or '').strip()
    if not query:
        return jsonify({'error': "'query' is required"}), 400
    item_type = data.get('type')
    if item_type is not None:
        item_type = item_type.strip().lower()
        if item_type not in {'idea', 'template', 'all', ''}:
            return jsonify({'error': "'type' must be one of: idea, template, all"}), 400
        if item_type in {'all', ''}:
            item_type = None
    top_k = data.get('top_k')
    try:
        top_k = int(top_k) if top_k is not None else 10
    except Exception:
        return jsonify({'error': "'top_k' must be an integer"}), 400
    top_k = max(1, min(top_k, 100))

    query_vec = EMBEDDER.embed(query)
    results = STORE.search(query_vec, item_type=item_type, top_k=top_k)
    return jsonify({'results': results})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)



def create_app():
    return app


@app.route('/search/ideas', methods=['POST'])
def _auto_stub_search_ideas():
    return 'Auto-generated stub for /search/ideas', 200


@app.route('/search/templates', methods=['POST'])
def _auto_stub_search_templates():
    return 'Auto-generated stub for /search/templates', 200


@app.route('/search/combined', methods=['POST'])
def _auto_stub_search_combined():
    return 'Auto-generated stub for /search/combined', 200
