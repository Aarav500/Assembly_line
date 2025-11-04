from flask import Blueprint, jsonify, request, render_template
from typing import Any, Dict

from .cloudinit import build_cloud_config
from .providers.registry import registry

api_bp = Blueprint("api", __name__)
web_bp = Blueprint("web", __name__)


@web_bp.get("/")
def index():
    return render_template("index.html")


@api_bp.get("/providers")
def list_providers():
    return jsonify({"providers": registry.list()})


@api_bp.post("/cloudinit/generate")
def generate_cloudinit():
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    try:
        cloud_init = build_cloud_config(payload or {})
        return jsonify({"ok": True, "cloud_init": cloud_init})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@api_bp.post("/provision")
def provision():
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    provider_name = payload.get("provider") or "dummy"
    provider = registry.get(provider_name)
    if not provider:
        return jsonify({"ok": False, "error": f"Unknown provider: {provider_name}"}), 400

    cloud_init_payload = payload.get("cloud_init")
    if isinstance(cloud_init_payload, dict):
        cloud_init = build_cloud_config(cloud_init_payload)
    elif isinstance(cloud_init_payload, str) and cloud_init_payload.strip().startswith("#cloud-config"):
        cloud_init = cloud_init_payload
    else:
        # try from fields
        cloud_init = build_cloud_config(payload.get("config") or {})

    meta = payload.get("meta") or {}

    try:
        instance = provider.create_instance(
            name=payload.get("name") or meta.get("name") or "vm",
            image=payload.get("image") or meta.get("image") or "generic",
            instance_type=payload.get("instance_type") or meta.get("instance_type") or "small",
            network=payload.get("network") or meta.get("network") or {},
            ssh_key=payload.get("ssh_key") or meta.get("ssh_key") or "",
            cloud_init=cloud_init,
            extra=payload.get("extra") or {},
        )
        return jsonify({"ok": True, "instance": instance, "cloud_init": cloud_init})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@api_bp.get("/instances")
def list_instances():
    # Aggregates from all providers
    instances = []
    for p in registry.list():
        provider = registry.get(p["name"])  # type: ignore
        if provider:
            instances.extend(provider.list_instances())
    return jsonify({"instances": instances})

