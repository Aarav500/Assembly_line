import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
from elasticsearch import Elasticsearch
import os

app = Flask(__name__)

# Configure Elasticsearch connection
ES_HOST = os.getenv('ELASTICSEARCH_HOST', 'localhost:9200')
es = None

try:
    es = Elasticsearch([ES_HOST])
except Exception as e:
    print(f"Elasticsearch connection error: {e}")

INDEX_NAME = 'documents'

@app.route('/health', methods=['GET'])
def health():
    es_status = 'connected' if es and es.ping() else 'disconnected'
    return jsonify({'status': 'ok', 'elasticsearch': es_status})

@app.route('/index', methods=['POST'])
def index_document():
    if not es:
        return jsonify({'error': 'Elasticsearch not connected'}), 503
    
    data = request.get_json()
    if not data or 'id' not in data or 'content' not in data:
        return jsonify({'error': 'Missing id or content'}), 400
    
    try:
        result = es.index(index=INDEX_NAME, id=data['id'], document=data)
        return jsonify({'success': True, 'result': result['result']}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/search', methods=['GET'])
def search():
    if not es:
        return jsonify({'error': 'Elasticsearch not connected'}), 503
    
    query = request.args.get('q', '')
    if not query:
        return jsonify({'error': 'Missing query parameter q'}), 400
    
    try:
        result = es.search(index=INDEX_NAME, body={
            'query': {
                'multi_match': {
                    'query': query,
                    'fields': ['content', 'title']
                }
            }
        })
        
        hits = [{
            'id': hit['_id'],
            'score': hit['_score'],
            'source': hit['_source']
        } for hit in result['hits']['hits']]
        
        return jsonify({'total': result['hits']['total']['value'], 'results': hits})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/delete/<doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    if not es:
        return jsonify({'error': 'Elasticsearch not connected'}), 503
    
    try:
        result = es.delete(index=INDEX_NAME, id=doc_id)
        return jsonify({'success': True, 'result': result['result']})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)


def create_app():
    return app
