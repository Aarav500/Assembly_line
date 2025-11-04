import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import io
import tempfile
from flask import Flask, request, jsonify, send_file
from scaffolder.manifest_loader import load_manifest
from scaffolder.helm_generator import HelmGenerator
from scaffolder.k8s_generator import K8sGenerator
from scaffolder.terraform_generator import TerraformGenerator
from scaffolder.utils import create_zip_from_dir, sanitize_name

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

@app.route('/generate', methods=['POST'])
def generate():
    try:
        raw = request.data
        if not raw:
            return jsonify({"error": "empty body"}), 400
        manifest = load_manifest(raw)
        # basic checks
        if 'project' not in manifest or 'name' not in manifest['project']:
            return jsonify({"error": "manifest.project.name is required"}), 400
        chart_name = sanitize_name(manifest['project']['name'])

        with tempfile.TemporaryDirectory() as tmpdir:
            # Generate Helm chart
            HelmGenerator().generate(tmpdir, manifest)
            # Generate K8s manifests
            K8sGenerator().generate(tmpdir, manifest)
            # Generate Terraform scaffold
            TerraformGenerator().generate(tmpdir, manifest)

            # Zip and send
            mem_zip = io.BytesIO()
            create_zip_from_dir(tmpdir, mem_zip)
            mem_zip.seek(0)
            filename = f"{chart_name}-scaffold.zip"
            return send_file(mem_zip, download_name=filename, mimetype='application/zip', as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)



def create_app():
    return app


@app.route('/scaffold', methods=['POST'])
def _auto_stub_scaffold():
    return 'Auto-generated stub for /scaffold', 200
