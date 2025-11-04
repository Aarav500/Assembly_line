import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
from secret_scanner import scanner, config as cfg, baseline as bl
import os

app = Flask(__name__)

CONFIG_PATH = os.environ.get("SECRETSCAN_CONFIG", ".secretscan.yml")
BASELINE_PATH = os.environ.get("SECRETSCAN_BASELINE", ".secrets.baseline.json")

conf = cfg.load_config(CONFIG_PATH)
base = bl.Baseline.load(BASELINE_PATH)

@app.get("/health")
def health():
    return jsonify({"status": "ok"})

@app.post("/scan")
def scan_endpoint():
    data = request.get_json(silent=True) or {}

    findings = []
    if "files" in data and isinstance(data["files"], list):
        for f in data["files"]:
            path = f.get("path") or f.get("filename") or "<memory>"
            content = f.get("content", "")
            findings.extend(scanner.scan_content(content, path, conf, base))
    elif "content" in data:
        path = data.get("filename") or "<memory>"
        content = data.get("content", "")
        findings = scanner.scan_content(content, path, conf, base)
    else:
        return jsonify({"error": "Provide 'content' and optional 'filename', or 'files': [{path, content}]"}), 400

    return jsonify({
        "findings": findings,
        "count": len(findings)
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))



def create_app():
    return app
