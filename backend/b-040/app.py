import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import traceback
from flask import Flask, request, jsonify, send_file
from dotenv import load_dotenv

from services.notion_service import export_to_notion
from services.google_docs_service import export_to_google_docs
from services.github_service import export_to_github_issue
from services.pdf_service import export_to_pdf
from services.markdown_service import export_to_markdown
from utils.path_utils import safe_filename
from config import get_settings

load_dotenv()

app = Flask(__name__)


def normalize_destination(dest: str) -> str:
    if not dest:
        return ''
    d = dest.strip().lower().replace(' ', '_').replace('-', '_')
    aliases = {
        'google_docs': 'google_docs',
        'googledocs': 'google_docs',
        'gdocs': 'google_docs',
        'docs': 'google_docs',
        'notion': 'notion',
        'github_issue': 'github_issue',
        'github': 'github_issue',
        'issue': 'github_issue',
        'pdf': 'pdf',
        'markdown': 'markdown',
        'md': 'markdown',
    }
    return aliases.get(d, d)


@app.get('/health')
def health():
    return jsonify({"ok": True})


@app.post('/export')
def export_endpoint():
    try:
        payload = request.get_json(silent=True) or {}
        destination = normalize_destination(payload.get('destination') or payload.get('format'))
        title = payload.get('title') or 'Untitled'
        content = payload.get('content') or ''
        options = payload.get('options') or {}

        if not destination:
            return jsonify({"error": "Missing 'destination' in request body"}), 400
        if destination not in {"notion", "google_docs", "github_issue", "pdf", "markdown"}:
            return jsonify({"error": f"Unsupported destination: {destination}"}), 400

        settings = get_settings()

        if destination == 'notion':
            result = export_to_notion(title=title, content=content, options=options, settings=settings)
            return jsonify({
                "status": "success",
                "destination": "notion",
                "id": result.get('id'),
                "url": result.get('url'),
            })

        if destination == 'google_docs':
            result = export_to_google_docs(title=title, content=content, options=options, settings=settings)
            return jsonify({
                "status": "success",
                "destination": "google_docs",
                "id": result.get('id'),
                "url": result.get('url'),
            })

        if destination == 'github_issue':
            result = export_to_github_issue(title=title, content=content, options=options, settings=settings)
            return jsonify({
                "status": "success",
                "destination": "github_issue",
                "id": result.get('number'),
                "url": result.get('url'),
            })

        if destination == 'pdf':
            file_path = export_to_pdf(title=title, content=content, options=options, settings=settings)
            filename = os.path.basename(file_path)
            return send_file(file_path, as_attachment=True, download_name=filename, mimetype='application/pdf')

        if destination == 'markdown':
            file_path = export_to_markdown(title=title, content=content, options=options, settings=settings)
            filename = os.path.basename(file_path)
            return send_file(file_path, as_attachment=True, download_name=filename, mimetype='text/markdown')

        return jsonify({"error": f"Unhandled destination: {destination}"}), 400

    except Exception as e:
        app.logger.exception("Export failed")
        return jsonify({
            "error": "Export failed",
            "message": str(e),
            "trace": traceback.format_exc(),
        }), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))



def create_app():
    return app


@app.route('/export/markdown', methods=['POST'])
def _auto_stub_export_markdown():
    return 'Auto-generated stub for /export/markdown', 200


@app.route('/export/github-issue', methods=['POST'])
def _auto_stub_export_github_issue():
    return 'Auto-generated stub for /export/github-issue', 200
