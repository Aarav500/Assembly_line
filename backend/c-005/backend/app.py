import io
import os
from pathlib import Path
from typing import Optional
from zipfile import ZipFile, ZIP_DEFLATED
from flask import Flask, jsonify, request, send_file, abort
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

ROOT = Path(__file__).resolve().parent.parent
SCAFFOLDS = {
    "react-native-expo": ROOT / "mobile" / "react-native-expo",
    "flutter-basic": ROOT / "mobile" / "flutter-basic",
}


def _zip_directory_to_bytes(dir_path: Path, root_name: Optional[str] = None) -> bytes:
    buf = io.BytesIO()
    with ZipFile(buf, "w", ZIP_DEFLATED) as zf:
        base = Path(root_name) if root_name else Path(dir_path.name)
        for path in dir_path.rglob("*"):
            if path.is_dir():
                continue
            rel = path.relative_to(dir_path)
            arc = base / rel
            # Ensure text files preserve LF endings as-is; write raw bytes
            with open(path, "rb") as f:
                zf.writestr(str(arc), f.read())
    buf.seek(0)
    return buf.read()


@app.get("/")
def index():
    return jsonify({
        "name": "mobile-scaffolds-react-native-flutter",
        "stack": "python, flask",
        "endpoints": [
            "/api/hello",
            "/api/time",
            "/scaffolds",
            "/scaffolds/<name>/archive.zip",
        ],
    })


@app.get("/api/hello")
def api_hello():
    who = request.args.get("who", "world")
    return jsonify({"message": f"Hello, {who}!", "ok": True})


@app.get("/api/time")
def api_time():
    import datetime as _dt
    now = _dt.datetime.utcnow().isoformat() + "Z"
    return jsonify({"utc": now})


@app.get("/scaffolds")
def list_scaffolds():
    base = request.host_url.rstrip("/")
    items = []
    for name, path in SCAFFOLDS.items():
        items.append({
            "name": name,
            "description": "React Native (Expo) scaffold" if "react-native" in name else "Flutter scaffold",
            "path": str(path.relative_to(ROOT)),
            "download_url": f"{base}/scaffolds/{name}/archive.zip",
        })
    return jsonify({"scaffolds": items})


@app.get("/scaffolds/<name>/archive.zip")
def download_scaffold(name: str):
    if name not in SCAFFOLDS:
        abort(404, description="Unknown scaffold")
    dir_path = SCAFFOLDS[name]
    if not dir_path.exists():
        abort(404, description="Scaffold directory missing")

    archive_bytes = _zip_directory_to_bytes(dir_path, root_name=name)
    return send_file(
        io.BytesIO(archive_bytes),
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"{name}.zip",
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
