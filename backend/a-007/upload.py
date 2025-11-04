import os
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename


upload_bp = Blueprint("upload", __name__)


@upload_bp.route("/upload", methods=["POST"])
def upload():
    try:
        if "file" not in request.files:
            return jsonify({"error": "file field required"}), 400
        f = request.files["file"]
        if f.filename == "":
            return jsonify({"error": "empty filename"}), 400
        filename = secure_filename(f.filename)

        # Demo: save to ./uploads (ephemeral)
        upload_dir = os.path.join(os.getcwd(), "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        path = os.path.join(upload_dir, filename)
        f.save(path)

        return jsonify({
            "ok": True,
            "filename": filename,
            "size": os.path.getsize(path),
        })
    except OSError as e:
        return jsonify({"error": f"File system error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500