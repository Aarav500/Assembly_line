import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
import uuid
from datetime import datetime
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from models import db, Dataset
from analysis import analyze_csv, preview_csv


def create_app():
    app = Flask(__name__)

    # Basic config
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(app.instance_path, 'catalog.db')}"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=int(os.environ.get("MAX_CONTENT_LENGTH", 100 * 1024 * 1024)),  # 100MB default
        UPLOAD_FOLDER=os.environ.get("UPLOAD_FOLDER", os.path.abspath(os.path.join(os.getcwd(), "data", "uploads"))),
        JSONIFY_PRETTYPRINT_REGULAR=False,
    )

    # Ensure folders exist
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "time": datetime.utcnow().isoformat() + "Z"})

    @app.route("/datasets", methods=["POST"])
    def create_dataset():
        if "file" not in request.files:
            return jsonify({"error": "No file part in the request. Use multipart/form-data with field 'file'."}), 400
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No selected file."}), 400

        original_name = secure_filename(file.filename)
        ext = os.path.splitext(original_name)[1]
        uid = str(uuid.uuid4())
        stored_name = f"{uid}{ext}"
        dest_path = os.path.join(app.config["UPLOAD_FOLDER"], stored_name)
        file.save(dest_path)
        size_bytes = os.path.getsize(dest_path)

        name = request.form.get("name") or os.path.splitext(original_name)[0]

        ds = Dataset(
            name=name,
            filename=stored_name,
            original_name=original_name,
            size_bytes=size_bytes,
            schema_json=None,
            quality_metrics_json=None,
            sample_rows_json=None,
            row_count=None,
            col_count=None,
        )
        db.session.add(ds)
        db.session.commit()

        return jsonify({
            "id": ds.id,
            "name": ds.name,
            "original_name": ds.original_name,
            "size_bytes": ds.size_bytes,
            "created_at": ds.created_at.isoformat() + "Z",
            "file": {
                "stored_name": ds.filename,
                "path": dest_path,
            },
        }), 201

    @app.route("/datasets", methods=["GET"])
    def list_datasets():
        datasets = Dataset.query.order_by(Dataset.created_at.desc()).all()
        items = []
        for ds in datasets:
            items.append({
                "id": ds.id,
                "name": ds.name,
                "original_name": ds.original_name,
                "size_bytes": ds.size_bytes,
                "row_count": ds.row_count,
                "col_count": ds.col_count,
                "created_at": ds.created_at.isoformat() + "Z",
                "updated_at": ds.updated_at.isoformat() + "Z",
            })
        return jsonify({"items": items, "count": len(items)})

    @app.route("/datasets/<int:ds_id>", methods=["GET"])
    def get_dataset(ds_id):
        ds = Dataset.query.get_or_404(ds_id)
        data = {
            "id": ds.id,
            "name": ds.name,
            "original_name": ds.original_name,
            "size_bytes": ds.size_bytes,
            "row_count": ds.row_count,
            "col_count": ds.col_count,
            "created_at": ds.created_at.isoformat() + "Z",
            "updated_at": ds.updated_at.isoformat() + "Z",
            "schema": json.loads(ds.schema_json) if ds.schema_json else None,
            "quality_metrics": json.loads(ds.quality_metrics_json) if ds.quality_metrics_json else None,
            "sample_rows": json.loads(ds.sample_rows_json) if ds.sample_rows_json else None,
        }
        return jsonify(data)

    @app.route("/datasets/<int:ds_id>/analyze", methods=["POST"])
    def analyze_dataset(ds_id):
        ds = Dataset.query.get_or_404(ds_id)
        # Parameters
        sample_size = int(request.args.get("sample_size", 10))
        read_rows_limit = request.args.get("read_rows_limit")
        read_rows_limit = int(read_rows_limit) if read_rows_limit is not None else None

        file_path = os.path.join(app.config["UPLOAD_FOLDER"], ds.filename)
        if not os.path.exists(file_path):
            return jsonify({"error": f"File not found on server: {ds.filename}"}), 404

        try:
            result = analyze_csv(file_path=file_path, sample_size=sample_size, read_rows_limit=read_rows_limit)
        except Exception as e:
            return jsonify({"error": f"Analysis failed: {str(e)}"}), 500

        ds.schema_json = json.dumps(result["schema"], ensure_ascii=False)
        ds.quality_metrics_json = json.dumps(result["quality_metrics"], ensure_ascii=False)
        ds.sample_rows_json = json.dumps(result["sample_rows"], ensure_ascii=False)
        ds.row_count = result.get("row_count")
        ds.col_count = result.get("col_count")
        db.session.commit()

        payload = {
            "id": ds.id,
            "name": ds.name,
            "row_count": ds.row_count,
            "col_count": ds.col_count,
            "schema": result["schema"],
            "quality_metrics": result["quality_metrics"],
            "sample_rows": result["sample_rows"],
        }
        return jsonify(payload)

    @app.route("/datasets/<int:ds_id>/preview", methods=["GET"])
    def preview_dataset(ds_id):
        ds = Dataset.query.get_or_404(ds_id)
        limit = int(request.args.get("limit", 50))
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], ds.filename)
        if not os.path.exists(file_path):
            return jsonify({"error": f"File not found on server: {ds.filename}"}), 404
        try:
            preview = preview_csv(file_path, limit=limit)
        except Exception as e:
            return jsonify({"error": f"Preview failed: {str(e)}"}), 500
        return jsonify({"columns": preview["columns"], "rows": preview["rows"], "limit": limit})

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=os.environ.get("FLASK_DEBUG", "0") == "1")

