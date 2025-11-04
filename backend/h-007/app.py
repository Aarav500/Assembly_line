import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import re
import json
from flask import Flask, request, jsonify, render_template
from services.citation_extractor import extract_citations
from services.provenance_linker import link_provenance
from services.text_loader import load_text_from_url, load_text_from_file


def create_app():
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/health", methods=["GET"]) 
    def health():
        return jsonify({"status": "ok"})

    @app.route("/api/extract-citations", methods=["POST"]) 
    def api_extract():
        payload = request.get_json(silent=True) or {}
        text = payload.get("text")
        url = payload.get("url")
        options = payload.get("options", {})

        if not text and not url and not request.files:
            return jsonify({"error": "Provide 'text', 'url', or upload a file."}), 400

        try:
            if not text and url:
                text = load_text_from_url(url)
            if not text and request.files:
                file = request.files.get("file")
                if file:
                    text = load_text_from_file(file)
        except Exception as e:
            return jsonify({"error": f"Failed to load text: {str(e)}"}), 400

        if not text:
            return jsonify({"error": "No text content available after loading."}), 400

        citations = extract_citations(text, options=options)
        return jsonify({"citations": citations})

    @app.route("/api/link-provenance", methods=["POST"]) 
    def api_link():
        payload = request.get_json(silent=True) or {}
        citations = payload.get("citations")
        if not citations:
            return jsonify({"error": "Provide 'citations' array to link provenance."}), 400
        enriched = link_provenance(citations)
        return jsonify({"citations": enriched})

    @app.route("/api/process", methods=["POST"]) 
    def api_process():
        payload = request.get_json(silent=True) or {}
        text = payload.get("text")
        url = payload.get("url")
        link = bool(payload.get("link_provenance", True))
        options = payload.get("options", {})

        if not text and not url and not request.files:
            return jsonify({"error": "Provide 'text', 'url', or upload a file."}), 400
        try:
            if not text and url:
                text = load_text_from_url(url)
            if not text and request.files:
                file = request.files.get("file")
                if file:
                    text = load_text_from_file(file)
        except Exception as e:
            return jsonify({"error": f"Failed to load text: {str(e)}"}), 400

        if not text:
            return jsonify({"error": "No text content available after loading."}), 400

        citations = extract_citations(text, options=options)
        if link:
            citations = link_provenance(citations)
        return jsonify({"citations": citations})

    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app = create_app()
    app.run(host="0.0.0.0", port=port, debug=debug)



@app.route('/provenance', methods=['POST'])
def _auto_stub_provenance():
    return 'Auto-generated stub for /provenance', 200


@app.route('/provenance/doc1/cite1', methods=['GET'])
def _auto_stub_provenance_doc1_cite1():
    return 'Auto-generated stub for /provenance/doc1/cite1', 200
