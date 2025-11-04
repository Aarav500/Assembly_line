from typing import Any, Dict
from flask import Flask, request, jsonify
import yaml
from .config import config
from .generators.argocd import generate_argocd_sync_job
from .generators.flux import generate_flux_reconcile_job
from .validators import validate_k8s_job_manifest, InputError


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_mapping({
        "DEBUG": config.DEBUG,
    })

    @app.route("/healthz", methods=["GET"])  # readiness/liveness probe
    def healthz():
        return jsonify({"status": "ok"})

    @app.route("/generate/argocd-sync-job", methods=["POST"])  # Generate Job YAML for ArgoCD sync
    def generate_argocd():
        try:
            payload: Dict[str, Any] = request.get_json(force=True)
        except Exception:
            return jsonify({"error": "Invalid or missing JSON"}), 400
        try:
            yml = generate_argocd_sync_job(payload)
        except InputError as ie:
            return jsonify({"error": str(ie)}), 400
        except Exception as e:
            return jsonify({"error": f"Failed to generate ArgoCD job: {e}"}), 500
        return jsonify({"kind": "Job", "yaml": yml})

    @app.route("/generate/flux-reconcile-job", methods=["POST"])  # Generate Job YAML for Flux reconcile
    def generate_flux():
        try:
            payload: Dict[str, Any] = request.get_json(force=True)
        except Exception:
            return jsonify({"error": "Invalid or missing JSON"}), 400
        try:
            yml = generate_flux_reconcile_job(payload)
        except InputError as ie:
            return jsonify({"error": str(ie)}), 400
        except Exception as e:
            return jsonify({"error": f"Failed to generate Flux job: {e}"}), 500
        return jsonify({"kind": "Job", "yaml": yml})

    @app.route("/validate/job", methods=["POST"])  # Validate a Job YAML/JSON manifest
    def validate_job():
        try:
            payload: Dict[str, Any] = request.get_json(force=True)
        except Exception:
            return jsonify({"error": "Invalid or missing JSON"}), 400

        manifest = None
        if isinstance(payload.get("manifest"), dict):
            manifest = payload["manifest"]
        elif isinstance(payload.get("yaml"), str):
            try:
                manifest = yaml.safe_load(payload["yaml"]) or {}
            except Exception as e:
                return jsonify({"valid": False, "errors": [f"YAML parse error: {e}"]}), 400
        else:
            return jsonify({"error": "Provide 'manifest' as object or 'yaml' as string"}), 400

        valid, errors = validate_k8s_job_manifest(manifest)
        return jsonify({"valid": valid, "errors": errors})

    return app


app = create_app()

