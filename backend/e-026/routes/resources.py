from flask import Blueprint, current_app, request
from services.providers.provider_registry import get_registered_providers
from utils.json_store import load_ingested_resources

resources_bp = Blueprint("resources", __name__)


def _aggregate_resources():
    providers = get_registered_providers()
    provider_resources = []
    for p in providers:
        try:
            provider_resources.extend(p.list_resources())
        except Exception as e:
            current_app.logger.exception("Provider %s failed: %s", p.name, e)
    ingested = load_ingested_resources(current_app.config["INGESTED_FILE"]) or []

    # Deduplicate by id with preference: ingested overrides provider entries
    agg = {}
    for r in provider_resources:
        agg[r.get("id") or f"{r.get('provider')}::{r.get('name')}"] = r
    for r in ingested:
        agg[r.get("id") or f"{r.get('provider')}::{r.get('name')}"] = r
    return list(agg.values())


@resources_bp.get("/resources")
def list_resources():
    resources = _aggregate_resources()
    # Optional filtering
    provider = request.args.get("provider")
    region = request.args.get("region")
    resource_type = request.args.get("type")

    def _match(r):
        if provider and r.get("provider") != provider:
            return False
        if region and r.get("region") != region:
            return False
        if resource_type and r.get("resource_type") != resource_type:
            return False
        return True

    filtered = [r for r in resources if _match(r)]
    return {"count": len(filtered), "resources": filtered}

