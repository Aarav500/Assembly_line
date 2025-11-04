import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from datetime import datetime
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_

from config import Config
from models import db, Document
from ingestion.parsers import extract_text_from_file, extract_from_url
from ingestion.repo import clone_and_extract_repo


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Ensure directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['REPO_FOLDER'], exist_ok=True)
    os.makedirs(os.path.dirname(app.config['SQLALCHEMY_DATABASE_PATH']), exist_ok=True)

    db.init_app(app)
    with app.app_context():
        db.create_all()

    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({"status": "ok"})

    @app.route('/ingest/upload', methods=['POST'])
    def ingest_upload():
        if 'files' not in request.files:
            return jsonify({"error": "No files part in the request"}), 400

        files = request.files.getlist('files')
        if not files:
            return jsonify({"error": "No files provided"}), 400

        saved = []
        errors = []

        for f in files:
            if f.filename == '':
                errors.append({"file": None, "error": "Empty filename"})
                continue

            filename = secure_filename(f.filename)
            ext = os.path.splitext(filename)[1].lower()
            if ext and (ext.lstrip('.') not in app.config['ALLOWED_EXTENSIONS']):
                errors.append({"file": filename, "error": f"Extension '{ext}' not allowed"})
                continue

            save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            # Avoid overwriting: add suffix if exists
            base, extn = os.path.splitext(save_path)
            i = 1
            while os.path.exists(save_path):
                save_path = f"{base}_{i}{extn}"
                i += 1

            f.save(save_path)

            try:
                parsed = extract_text_from_file(save_path)
                if not parsed or not parsed.get('content'):
                    errors.append({"file": filename, "error": "Unable to extract content"})
                    continue

                doc = Document(
                    source_type='file',
                    source=save_path,
                    title=parsed.get('title') or filename,
                    content=parsed.get('content'),
                    meta=json.dumps({
                        "filename": filename,
                        "path": save_path,
                        "mime": parsed.get('mime'),
                        "extra": parsed.get('meta', {})
                    })
                )
                db.session.add(doc)
                db.session.commit()
                saved.append(doc.to_dict(include_content=False))
            except Exception as e:
                errors.append({"file": filename, "error": str(e)})

        return jsonify({"saved": saved, "errors": errors})

    @app.route('/ingest/url', methods=['POST'])
    def ingest_url():
        data = request.get_json(silent=True) or {}
        urls = data.get('urls') or []
        if not isinstance(urls, list) or not urls:
            return jsonify({"error": "Provide 'urls' as a non-empty list"}), 400

        saved = []
        errors = []
        for url in urls:
            try:
                parsed = extract_from_url(url)
                if not parsed or not parsed.get('content'):
                    errors.append({"url": url, "error": "Unable to extract content"})
                    continue

                doc = Document(
                    source_type='url',
                    source=url,
                    title=parsed.get('title') or url,
                    content=parsed.get('content'),
                    meta=json.dumps({
                        "url": url,
                        "mime": parsed.get('mime'),
                        "extra": parsed.get('meta', {})
                    })
                )
                db.session.add(doc)
                db.session.commit()
                saved.append(doc.to_dict(include_content=False))
            except Exception as e:
                errors.append({"url": url, "error": str(e)})

        return jsonify({"saved": saved, "errors": errors})

    @app.route('/ingest/repo', methods=['POST'])
    def ingest_repo():
        data = request.get_json(silent=True) or {}
        repo_url = data.get('repo_url')
        branch = data.get('branch')
        include_ext = data.get('include_ext')  # optional list
        exclude_dirs = data.get('exclude_dirs')  # optional list
        max_files = data.get('max_files')  # optional int

        if not repo_url:
            return jsonify({"error": "Missing 'repo_url'"}), 400

        try:
            extracted = clone_and_extract_repo(
                repo_url=repo_url,
                base_dir=current_app.config['REPO_FOLDER'] if 'current_app' in globals() else app.config['REPO_FOLDER'],
                branch=branch,
                include_ext=include_ext,
                exclude_dirs=exclude_dirs,
                max_files=max_files
            )
        except Exception as e:
            return jsonify({"error": str(e)}), 400

        saved = []
        for item in extracted.get('files', []):
            doc = Document(
                source_type='repo',
                source=os.path.join(extracted.get('local_path', ''), item.get('relative_path', '')),
                title=item.get('relative_path'),
                content=item.get('content'),
                meta=json.dumps({
                    "repo_url": repo_url,
                    "branch": extracted.get('branch'),
                    "commit": extracted.get('commit'),
                    "relative_path": item.get('relative_path'),
                    "language": item.get('language'),
                })
            )
            db.session.add(doc)
            saved.append(doc)
        db.session.commit()

        return jsonify({
            "repo": {
                "repo_url": repo_url,
                "branch": extracted.get('branch'),
                "commit": extracted.get('commit'),
                "files_ingested": len(saved)
            },
            "documents": [d.to_dict(include_content=False) for d in saved]
        })

    @app.route('/documents', methods=['GET'])
    def list_documents():
        q = request.args.get('q')
        source_type = request.args.get('source_type')
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))

        query = Document.query
        if source_type:
            query = query.filter(Document.source_type == source_type)
        if q:
            like = f"%{q}%"
            query = query.filter(or_(Document.title.ilike(like), Document.content.ilike(like)))

        total = query.count()
        items = query.order_by(Document.created_at.desc()).offset(offset).limit(limit).all()
        return jsonify({
            "total": total,
            "count": len(items),
            "items": [d.to_dict(include_content=False) for d in items]
        })

    @app.route('/documents/<int:doc_id>', methods=['GET'])
    def get_document(doc_id):
        doc = Document.query.get_or_404(doc_id)
        include_content = request.args.get('include_content', '1') not in ('0', 'false', 'no')
        return jsonify(doc.to_dict(include_content=include_content))

    @app.route('/documents/<int:doc_id>', methods=['DELETE'])
    def delete_document(doc_id):
        doc = Document.query.get_or_404(doc_id)
        db.session.delete(doc)
        db.session.commit()
        return jsonify({"deleted": doc_id})

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))



@app.route('/ingest/file', methods=['POST'])
def _auto_stub_ingest_file():
    return 'Auto-generated stub for /ingest/file', 200
