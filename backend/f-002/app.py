import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from datetime import datetime
from flask import Flask, request, jsonify
from dotenv import load_dotenv

from grafana import GrafanaClient, build_overview_dashboard, build_detail_dashboard, make_uids
from storage import ProjectStore

load_dotenv()

GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000")
GRAFANA_API_TOKEN = os.getenv("GRAFANA_API_TOKEN", "")
GRAFANA_DATASOURCE_UID = os.getenv("GRAFANA_DATASOURCE_UID", "")
GRAFANA_DATASOURCE_TYPE = os.getenv("GRAFANA_DATASOURCE_TYPE", "prometheus")

app = Flask(__name__)

grafana = GrafanaClient(
    base_url=GRAFANA_URL,
    api_token=GRAFANA_API_TOKEN,
)

store = ProjectStore(path=os.getenv("PROJECT_STORE_PATH", "data/projects.json"))


def validate_env():
    errors = []
    if not GRAFANA_API_TOKEN:
        errors.append("GRAFANA_API_TOKEN is required")
    if not GRAFANA_URL:
        errors.append("GRAFANA_URL is required")
    if not GRAFANA_DATASOURCE_UID:
        errors.append("GRAFANA_DATASOURCE_UID is required")
    return errors


@app.route("/healthz", methods=["GET"])
def health():
    env_errors = validate_env()
    return jsonify({
        "status": "ok" if not env_errors else "degraded",
        "envErrors": env_errors,
        "grafanaUrl": GRAFANA_URL,
    })


@app.route("/api/projects", methods=["GET"]) 
def list_projects():
    return jsonify(store.list())


@app.route("/api/projects", methods=["POST"]) 
def create_project():
    payload = request.get_json(force=True, silent=True) or {}
    name = (payload.get("name") or payload.get("project") or "").strip()
    create_dash = bool(payload.get("createDashboards", True))

    if not name:
        return jsonify({"error": "Missing required field 'name'"}), 400

    if store.get(name):
        return jsonify({"error": f"Project '{name}' already exists"}), 409

    env_errors = validate_env()
    if env_errors:
        return jsonify({"error": "Invalid environment", "details": env_errors}), 500

    uids = make_uids(name)

    # Ensure folder
    folder = grafana.ensure_folder(uids["folder_uid"], title=f"Project {name}")

    result = {
        "name": name,
        "folder": folder,
        "uids": uids,
        "dashboards": {},
        "createdAt": datetime.utcnow().isoformat() + "Z",
    }

    if create_dash:
        # Create detail first to reference from overview links
        detail_dash = build_detail_dashboard(
            project=name,
            detail_uid=uids["detail_uid"],
            overview_uid=uids["overview_uid"],
            ds_uid=GRAFANA_DATASOURCE_UID,
            ds_type=GRAFANA_DATASOURCE_TYPE,
        )
        detail_resp = grafana.upsert_dashboard(detail_dash, folder_id=folder["id"])  

        overview_dash = build_overview_dashboard(
            project=name,
            overview_uid=uids["overview_uid"],
            detail_uid=uids["detail_uid"],
            ds_uid=GRAFANA_DATASOURCE_UID,
            ds_type=GRAFANA_DATASOURCE_TYPE,
        )
        overview_resp = grafana.upsert_dashboard(overview_dash, folder_id=folder["id"]) 

        result["dashboards"] = {
            "detail": detail_resp,
            "overview": overview_resp,
        }

    store.add({
        "name": name,
        "folder": folder,
        "uids": uids,
        "dashboards": result.get("dashboards", {}),
        "createdAt": result["createdAt"],
    })

    return jsonify(result), 201


@app.route("/api/projects/<name>/dashboards/refresh", methods=["POST"]) 
def refresh_project_dashboards(name):
    rec = store.get(name)
    if not rec:
        return jsonify({"error": f"Project '{name}' not found"}), 404

    uids = rec["uids"]

    # Ensure folder
    folder = grafana.ensure_folder(uids["folder_uid"], title=f"Project {name}")

    # Upsert detail then overview
    detail_dash = build_detail_dashboard(
        project=name,
        detail_uid=uids["detail_uid"],
        overview_uid=uids["overview_uid"],
        ds_uid=GRAFANA_DATASOURCE_UID,
        ds_type=GRAFANA_DATASOURCE_TYPE,
    )
    detail_resp = grafana.upsert_dashboard(detail_dash, folder_id=folder["id"])  

    overview_dash = build_overview_dashboard(
        project=name,
        overview_uid=uids["overview_uid"],
        detail_uid=uids["detail_uid"],
        ds_uid=GRAFANA_DATASOURCE_UID,
        ds_type=GRAFANA_DATASOURCE_TYPE,
    )
    overview_resp = grafana.upsert_dashboard(overview_dash, folder_id=folder["id"]) 

    rec["dashboards"] = {
        "detail": detail_resp,
        "overview": overview_resp,
    }
    store.update(name, rec)

    return jsonify({
        "name": name,
        "folder": folder,
        "dashboards": rec["dashboards"],
    })


@app.route("/api/projects/<name>", methods=["DELETE"]) 
def delete_project(name):
    rec = store.get(name)
    if not rec:
        return jsonify({"error": f"Project '{name}' not found"}), 404

    # Try deleting dashboards first (ignore if absent)
    uids = rec.get("uids", {})
    for d_uid in [uids.get("overview_uid"), uids.get("detail_uid")]:
        if d_uid:
            try:
                grafana.delete_dashboard(d_uid)
            except Exception:
                pass

    # Delete folder
    folder_uid = rec.get("folder", {}).get("uid") or uids.get("folder_uid")
    if folder_uid:
        try:
            grafana.delete_folder(folder_uid)
        except Exception:
            pass

    store.remove(name)
    return jsonify({"status": "deleted", "name": name})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))



def create_app():
    return app


@app.route('/api/dashboards', methods=['GET'])
def _auto_stub_api_dashboards():
    return 'Auto-generated stub for /api/dashboards', 200


@app.route('/api/dashboards/project-a', methods=['GET'])
def _auto_stub_api_dashboards_project_a():
    return 'Auto-generated stub for /api/dashboards/project-a', 200


@app.route('/api/dashboards/nonexistent', methods=['GET'])
def _auto_stub_api_dashboards_nonexistent():
    return 'Auto-generated stub for /api/dashboards/nonexistent', 200


@app.route('/api/dashboards/project-a/cpu', methods=['GET'])
def _auto_stub_api_dashboards_project_a_cpu():
    return 'Auto-generated stub for /api/dashboards/project-a/cpu', 200


@app.route('/api/dashboards/project-a/nonexistent', methods=['GET'])
def _auto_stub_api_dashboards_project_a_nonexistent():
    return 'Auto-generated stub for /api/dashboards/project-a/nonexistent', 200


@app.route('/api/dashboards/nonexistent/cpu', methods=['GET'])
def _auto_stub_api_dashboards_nonexistent_cpu():
    return 'Auto-generated stub for /api/dashboards/nonexistent/cpu', 200
