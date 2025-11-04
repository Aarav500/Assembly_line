import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from flask import Flask, request, jsonify, render_template
from werkzeug.middleware.proxy_fix import ProxyFix

from config import (
    DATA_DIR,
    EXPORT_DIR,
    QUALITY_THRESHOLD,
    SOURCE_LANG_DEFAULT,
    SUPPORTED_LANGS_DEFAULT,
)
from translations.storage import (
    ensure_dirs,
    load_project,
    save_project,
    set_source_strings,
    set_languages,
    upsert_translation_entry,
    export_locales,
)
from translations.providers import get_translation_provider
from translations.tasks import translate_all_missing


def create_app():
    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app)

    ensure_dirs()

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/status", methods=["GET"])
    def api_status():
        project = load_project()
        return jsonify(project)

    @app.route("/api/source", methods=["POST"])
    def api_set_source():
        data = request.get_json(force=True, silent=True) or {}
        strings = data.get("strings")
        source_lang = data.get("source_lang", SOURCE_LANG_DEFAULT)
        if not isinstance(strings, dict):
            return jsonify({"error": "strings must be an object mapping keys to source text"}), 400
        project = load_project()
        project = set_source_strings(project, strings, source_lang)
        save_project(project)
        return jsonify({"ok": True, "source_lang": project.get("source_lang"), "count": len(strings)})

    @app.route("/api/languages", methods=["POST"])
    def api_set_languages():
        data = request.get_json(force=True, silent=True) or {}
        languages = data.get("languages")
        if not isinstance(languages, list) or not all(isinstance(l, str) for l in languages):
            return jsonify({"error": "languages must be an array of language codes"}), 400
        project = load_project()
        project = set_languages(project, languages)
        save_project(project)
        return jsonify({"ok": True, "languages": project.get("languages")})

    @app.route("/api/translate", methods=["POST"]) 
    def api_translate():
        data = request.get_json(force=True, silent=True) or {}
        target_languages = data.get("languages")  # optional subset
        force = bool(data.get("force", False))
        project = load_project()
        provider = get_translation_provider()
        summary = translate_all_missing(project, provider, QUALITY_THRESHOLD, target_languages=target_languages, force=force)
        save_project(project)
        return jsonify({"ok": True, "summary": summary})

    @app.route("/api/approve", methods=["POST"]) 
    def api_approve():
        data = request.get_json(force=True, silent=True) or {}
        lang = data.get("lang")
        key = data.get("key")
        text = data.get("text")
        if not (lang and key and isinstance(text, str)):
            return jsonify({"error": "Missing lang, key, or text"}), 400
        project = load_project()
        upsert_translation_entry(project, lang, key, text=text, status="approved", score=1.0, issues=[])
        save_project(project)
        return jsonify({"ok": True})

    @app.route("/api/reject", methods=["POST"]) 
    def api_reject():
        data = request.get_json(force=True, silent=True) or {}
        lang = data.get("lang")
        key = data.get("key")
        reason = data.get("reason", "manual_reject")
        if not (lang and key):
            return jsonify({"error": "Missing lang or key"}), 400
        project = load_project()
        entry = project.setdefault("translations", {}).setdefault(lang, {}).setdefault(key, {})
        entry["status"] = "rejected"
        issues = entry.get("issues", [])
        if reason not in issues:
            issues.append(reason)
        entry["issues"] = issues
        save_project(project)
        return jsonify({"ok": True})

    @app.route("/api/update", methods=["POST"]) 
    def api_update():
        data = request.get_json(force=True, silent=True) or {}
        lang = data.get("lang")
        key = data.get("key")
        text = data.get("text")
        status = data.get("status")  # optional
        if not (lang and key and isinstance(text, str)):
            return jsonify({"error": "Missing lang, key, or text"}), 400
        project = load_project()
        upsert_translation_entry(project, lang, key, text=text, status=status or "edited")
        save_project(project)
        return jsonify({"ok": True})

    @app.route("/api/export", methods=["GET"]) 
    def api_export():
        project = load_project()
        out_dir = EXPORT_DIR
        os.makedirs(out_dir, exist_ok=True)
        files = export_locales(project, out_dir)
        return jsonify({"ok": True, "files": files})

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)



@app.route('/supported-languages', methods=['GET'])
def _auto_stub_supported_languages():
    return 'Auto-generated stub for /supported-languages', 200
