import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv

from app.tasks.export_tasks import export_task
from app.tasks.import_tasks import import_task
from app.celery_app import celery_app


def create_app() -> Flask:
    load_dotenv()
    app = Flask(__name__)

    @app.route("/export", methods=["POST"])
    def export_endpoint():
        data = request.get_json(force=True)
        input_path = data.get("input_path")
        output_path = data.get("output_path")
        output_format = data.get("output_format")
        options = data.get("options", {})
        if not input_path:
            return jsonify({"error": "input_path is required"}), 400
        task = export_task.apply_async(args=[input_path, output_path, output_format, options])
        return jsonify({"task_id": task.id, "status_url": f"/tasks/{task.id}"}), 202

    @app.route("/import", methods=["POST"])
    def import_endpoint():
        data = request.get_json(force=True)
        file_path = data.get("file_path")
        dest_dir = data.get("dest_dir")
        schema = data.get("schema", {})
        options = data.get("options", {})
        if not file_path:
            return jsonify({"error": "file_path is required"}), 400
        task = import_task.apply_async(args=[file_path, dest_dir, schema, options])
        return jsonify({"task_id": task.id, "status_url": f"/tasks/{task.id}"}), 202

    @app.route("/tasks/<task_id>", methods=["GET"])
    def task_status(task_id):
        result = celery_app.AsyncResult(task_id)
        response = {"task_id": task_id, "state": result.state}
        if result.state == "PENDING":
            response.update({"current": 0, "total": 0, "percent": 0.0})
        elif result.state != "FAILURE":
            meta = result.info or {}
            response.update(meta)
        else:
            response.update({"error": str(result.info)})
        return jsonify(response)

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"})

    return app

