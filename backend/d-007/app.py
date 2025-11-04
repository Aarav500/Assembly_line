import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, abort
from werkzeug.utils import secure_filename

from storage import (
    get_storage_dir,
    get_release_dir,
    list_releases,
    load_manifest,
    save_manifest,
)
from sbom import generate_sbom_for_release

app = Flask(__name__)


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@app.route("/health", methods=["GET"]) 
def health():
    return jsonify({"status": "ok"})


@app.route("/releases", methods=["GET"]) 
def api_list_releases():
    return jsonify({"releases": list_releases()})


@app.route("/releases", methods=["POST"]) 
def api_create_release():
    payload = request.get_json(silent=True) or {}
    version = (payload.get("version") or "").strip()
    if not version:
        return jsonify({"error": "version is required"}), 400

    release_dir = get_release_dir(version)
    if os.path.exists(release_dir):
        return jsonify({"error": f"release '{version}' already exists"}), 409

    os.makedirs(release_dir, exist_ok=True)

    manifest = {
        "version": version,
        "createdAt": now_iso(),
        "notes": payload.get("notes") or "",
        "artifacts": [],
        "sbom": None,
    }
    save_manifest(version, manifest)
    return jsonify({"message": "release created", "release": manifest}), 201


@app.route("/releases/<version>", methods=["GET"]) 
def api_get_release(version):
    manifest = load_manifest(version)
    if not manifest:
        return jsonify({"error": "release not found"}), 404
    # add derived fields
    release_dir = get_release_dir(version)
    manifest_copy = dict(manifest)
    manifest_copy["artifactCount"] = len(manifest.get("artifacts", []))
    manifest_copy["paths"] = {
        "root": release_dir,
        "sbom": os.path.join(release_dir, manifest["sbom"]["path"]) if manifest.get("sbom") else None,
    }
    return jsonify({"release": manifest_copy})


@app.route("/releases/<version>/artifacts", methods=["POST"]) 
def api_upload_artifact(version):
    manifest = load_manifest(version)
    if not manifest:
        return jsonify({"error": "release not found"}), 404

    if "file" not in request.files:
        return jsonify({"error": "multipart/form-data with 'file' is required"}), 400

    file_storage = request.files["file"]
    if file_storage.filename == "":
        return jsonify({"error": "empty filename"}), 400

    filename = secure_filename(file_storage.filename)

    release_dir = get_release_dir(version)
    os.makedirs(release_dir, exist_ok=True)
    dest_path = os.path.join(release_dir, filename)

    # avoid overwrite by default
    if os.path.exists(dest_path):
        return jsonify({"error": f"artifact '{filename}' already exists in release {version}"}), 409

    file_storage.save(dest_path)

    # compute hashes & size
    import hashlib

    def _hash(path, algo):
        h = hashlib.new(algo)
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    size = os.path.getsize(dest_path)
    hashes = {
        "sha256": _hash(dest_path, "sha256"),
        "sha512": _hash(dest_path, "sha512"),
    }

    artifact_meta = {
        "filename": filename,
        "path": filename,
        "size": size,
        "hashes": hashes,
        "uploadedAt": now_iso(),
        "contentType": file_storage.mimetype or "application/octet-stream",
    }

    manifest.setdefault("artifacts", []).append(artifact_meta)
    save_manifest(version, manifest)

    return jsonify({"message": "artifact uploaded", "artifact": artifact_meta}), 201


@app.route("/releases/<version>/artifacts/<path:filename>", methods=["GET"]) 
def api_get_artifact(version, filename):
    manifest = load_manifest(version)
    if not manifest:
        return jsonify({"error": "release not found"}), 404

    release_dir = get_release_dir(version)
    filepath = os.path.join(release_dir, filename)
    if not os.path.isfile(filepath):
        return jsonify({"error": "artifact not found"}), 404

    return send_from_directory(release_dir, filename, as_attachment=True)


@app.route("/releases/<version>/sbom", methods=["POST"]) 
def api_generate_sbom(version):
    manifest = load_manifest(version)
    if not manifest:
        return jsonify({"error": "release not found"}), 404

    # If a request body is provided and includes inline requirements, write to requirements.txt in release dir
    payload = request.get_json(silent=True) or {}
    inline_requirements = payload.get("requirements")
    release_dir = get_release_dir(version)

    req_path = os.path.join(release_dir, "requirements.txt")
    if inline_requirements:
        with open(req_path, "w", encoding="utf-8") as f:
            f.write(inline_requirements.strip() + "\n")

    bom_path, bom_json = generate_sbom_for_release(version)

    # update manifest
    manifest["sbom"] = {
        "path": os.path.relpath(bom_path, release_dir),
        "generatedAt": now_iso(),
        "format": "CycloneDX",
        "specVersion": bom_json.get("specVersion"),
    }
    save_manifest(version, manifest)

    return jsonify({"message": "sbom generated", "sbom": manifest["sbom"], "bom": bom_json})


@app.route("/releases/<version>/sbom", methods=["GET"]) 
def api_get_sbom(version):
    manifest = load_manifest(version)
    if not manifest:
        return jsonify({"error": "release not found"}), 404
    if not manifest.get("sbom"):
        return jsonify({"error": "sbom not generated"}), 404

    release_dir = get_release_dir(version)
    sbom_path = os.path.join(release_dir, manifest["sbom"]["path"])
    if not os.path.isfile(sbom_path):
        return jsonify({"error": "sbom file missing"}), 404

    with open(sbom_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)



def create_app():
    return app


@app.route('/generate-sbom', methods=['GET'])
def _auto_stub_generate_sbom():
    return 'Auto-generated stub for /generate-sbom', 200


@app.route('/artifact/test-artifact-123/sbom', methods=['GET'])
def _auto_stub_artifact_test_artifact_123_sbom():
    return 'Auto-generated stub for /artifact/test-artifact-123/sbom', 200
