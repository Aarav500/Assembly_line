import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import uuid
import json
import shutil
import zipfile
from flask import Flask, request, jsonify

from src.indexer import ProjectIndexer
from src.search import SearchEngine
from src.faq import FAQGenerator
import config

app = Flask(__name__)

# Ensure data directory exists
os.makedirs(config.DATA_DIR, exist_ok=True)

indexer = ProjectIndexer()
engine = SearchEngine(index_path=config.INDEX_FILE)
faq_generator = FAQGenerator()

# Try to load existing index
engine.load()


def save_faq(faq_items):
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(config.FAQ_FILE, 'w', encoding='utf-8') as f:
        json.dump({"faq": faq_items}, f, indent=2, ensure_ascii=False)


def load_faq():
    if os.path.exists(config.FAQ_FILE):
        with open(config.FAQ_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f).get('faq', [])
            except Exception:
                return []
    return []


@app.get('/health')
def health():
    return jsonify({"status": "ok", "indexed": engine.num_documents()})


@app.post('/index')
def index_project():
    # Accept either a JSON body with {"path": "..."} or a zip file upload under form-data key 'archive'
    project_name = request.form.get('project_name') or (request.json or {}).get('project_name')

    extraction_path = None
    docs = []

    # Case 1: File upload
    if 'archive' in request.files:
        archive = request.files['archive']
        if not archive.filename.lower().endswith('.zip'):
            return jsonify({"error": "Only .zip archives are supported"}), 400
        upload_dir = os.path.join(config.DATA_DIR, 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        token = str(uuid.uuid4())
        archive_path = os.path.join(upload_dir, f'{token}.zip')
        archive.save(archive_path)
        extraction_path = os.path.join(upload_dir, token)
        os.makedirs(extraction_path, exist_ok=True)
        with zipfile.ZipFile(archive_path, 'r') as z:
            z.extractall(extraction_path)
        # Prefer a top-level directory if single folder inside
        base_path = extraction_path
        entries = os.listdir(extraction_path)
        if len(entries) == 1 and os.path.isdir(os.path.join(extraction_path, entries[0])):
            base_path = os.path.join(extraction_path, entries[0])
        docs = indexer.index_path(base_path)
        # Best-effort project name
        if not project_name:
            project_name = os.path.basename(os.path.normpath(base_path))
    else:
        # Case 2: JSON path
        body = request.get_json(silent=True) or {}
        path = body.get('path')
        if not path:
            return jsonify({"error": "Provide either a zip archive (form-data: archive) or JSON body with 'path'"}), 400
        if not os.path.exists(path):
            return jsonify({"error": f"Path does not exist: {path}"}), 400
        docs = indexer.index_path(path)
        if not project_name:
            project_name = os.path.basename(os.path.normpath(path))

    if not docs:
        return jsonify({"error": "No indexable content found in the provided project."}), 400

    engine.build(docs)
    engine.save()

    faq_items = faq_generator.generate(docs, project_name or 'the project')
    save_faq(faq_items)

    # Clean up extracted temp if any
    if extraction_path and os.path.isdir(extraction_path):
        try:
            shutil.rmtree(extraction_path)
        except Exception:
            pass

    return jsonify({
        "project": project_name,
        "indexed_documents": engine.num_documents(),
        "faq_count": len(faq_items),
        "message": "Indexing complete"
    })


@app.get('/search')
def search():
    q = request.args.get('q', '').strip()
    try:
        k = int(request.args.get('k', '8'))
    except ValueError:
        k = 8
    if not q:
        return jsonify({"error": "Missing query parameter 'q'"}), 400
    if engine.num_documents() == 0:
        return jsonify({"error": "No index available. POST /index first."}), 400
    results = engine.query(q, top_k=k)
    return jsonify({"query": q, "results": results})


@app.get('/faq')
def faq():
    data = load_faq()
    return jsonify({"faq": data, "count": len(data)})


@app.get('/kb')
def kb_items():
    items = engine.get_kb_items()
    return jsonify({"items": items, "count": len(items)})


@app.post('/reset')
def reset():
    removed = []
    for fpath in [config.INDEX_FILE, config.FAQ_FILE]:
        if os.path.exists(fpath):
            try:
                os.remove(fpath)
                removed.append(os.path.basename(fpath))
            except Exception:
                pass
    engine.reset()
    return jsonify({"message": "Reset complete", "removed": removed})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '5000')), debug=True)



def create_app():
    return app


@app.route('/generate', methods=['POST'])
def _auto_stub_generate():
    return 'Auto-generated stub for /generate', 200


@app.route('/query?q=configuration', methods=['GET'])
def _auto_stub_query_q_configuration():
    return 'Auto-generated stub for /query?q=configuration', 200
