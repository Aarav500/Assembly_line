import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from adapters.loki_adapter import LokiAdapter
from adapters.elastic_adapter import ElasticAdapter
from services.policy_service import PolicyService

load_dotenv()

app = Flask(__name__)

CONFIG_PATH = os.environ.get("APP_CONFIG_PATH", "config/config.yaml")
RUNTIME_CONFIG_PATH = os.environ.get("LOKI_RUNTIME_CONFIG_PATH", "generated/loki-runtime-config.yaml")
LOKI_ADMIN_URL = os.environ.get("LOKI_ADMIN_URL")

ES_URL = os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200")
ES_USERNAME = os.environ.get("ELASTICSEARCH_USERNAME")
ES_PASSWORD = os.environ.get("ELASTICSEARCH_PASSWORD")
ES_API_KEY = os.environ.get("ELASTICSEARCH_API_KEY")
ES_VERIFY_SSL = os.environ.get("ELASTICSEARCH_VERIFY_SSL", "true").lower() == "true"

policy_service = PolicyService(config_path=CONFIG_PATH)
loki_adapter = LokiAdapter(runtime_config_path=RUNTIME_CONFIG_PATH, admin_url=LOKI_ADMIN_URL)
elastic_adapter = ElasticAdapter(
    base_url=ES_URL,
    username=ES_USERNAME,
    password=ES_PASSWORD,
    api_key=ES_API_KEY,
    verify_ssl=ES_VERIFY_SSL,
)


@app.route("/health", methods=["GET"]) 
def health():
    return jsonify({"status": "ok"})


@app.route("/policies", methods=["GET"]) 
def list_policies():
    cfg = policy_service.load()
    return jsonify({
        "loki": cfg.get("loki", {}).get("tenants", []),
        "elastic": cfg.get("elastic", {}).get("policies", []),
    })


@app.route("/policies", methods=["POST"]) 
def add_policy():
    body = request.get_json(force=True, silent=False)
    ptype = body.get("type")
    if ptype == "loki_tenant":
        tenant_id = body.get("id")
        retention_days = body.get("retention_days")
        if not tenant_id or retention_days is None:
            return jsonify({"error": "id and retention_days required"}), 400
        cfg = policy_service.load()
        loki_cfg = cfg.setdefault("loki", {})
        tenants = loki_cfg.setdefault("tenants", [])
        # replace if exists
        updated = False
        for t in tenants:
            if t.get("id") == tenant_id:
                t["retention_days"] = int(retention_days)
                updated = True
                break
        if not updated:
            tenants.append({"id": tenant_id, "retention_days": int(retention_days)})
        policy_service.save(cfg)
        return jsonify({"status": "ok", "tenant": tenant_id})

    if ptype == "elastic_ilm":
        name = body.get("name")
        delete_after_days = body.get("delete_after_days")
        if not name or delete_after_days is None:
            return jsonify({"error": "name and delete_after_days required"}), 400
        hot_days = body.get("hot_days")
        warm_days = body.get("warm_days")
        index_pattern = body.get("index_pattern")
        cfg = policy_service.load()
        elastic_cfg = cfg.setdefault("elastic", {})
        policies = elastic_cfg.setdefault("policies", [])
        found = False
        for p in policies:
            if p.get("name") == name:
                p["delete_after_days"] = int(delete_after_days)
                if hot_days is not None:
                    p["hot_days"] = int(hot_days)
                if warm_days is not None:
                    p["warm_days"] = int(warm_days)
                if index_pattern is not None:
                    p["index_pattern"] = index_pattern
                found = True
                break
        if not found:
            policy = {
                "name": name,
                "delete_after_days": int(delete_after_days)
            }
            if hot_days is not None:
                policy["hot_days"] = int(hot_days)
            if warm_days is not None:
                policy["warm_days"] = int(warm_days)
            if index_pattern is not None:
                policy["index_pattern"] = index_pattern
            policies.append(policy)
        policy_service.save(cfg)
        return jsonify({"status": "ok", "policy": name})

    return jsonify({"error": "unsupported type"}), 400


@app.route("/policies/<ptype>/<name>", methods=["DELETE"]) 
def delete_policy(ptype, name):
    cfg = policy_service.load()
    if ptype == "loki_tenant":
        loki_cfg = cfg.get("loki", {})
        tenants = loki_cfg.get("tenants", [])
        tenants = [t for t in tenants if t.get("id") != name]
        loki_cfg["tenants"] = tenants
        cfg["loki"] = loki_cfg
        policy_service.save(cfg)
        return jsonify({"status": "ok"})

    if ptype == "elastic_ilm":
        elastic_cfg = cfg.get("elastic", {})
        policies = elastic_cfg.get("policies", [])
        policies = [p for p in policies if p.get("name") != name]
        elastic_cfg["policies"] = policies
        cfg["elastic"] = elastic_cfg
        policy_service.save(cfg)
        return jsonify({"status": "ok"})

    return jsonify({"error": "unsupported type"}), 400


@app.route("/apply", methods=["POST"]) 
def apply_policies():
    cfg = policy_service.load()
    results = {"loki": {}, "elastic": {}}

    # Apply Loki runtime overrides
    loki_cfg = cfg.get("loki", {})
    tenants = loki_cfg.get("tenants", [])
    default_ret = loki_cfg.get("default_retention_days")
    try:
        content = loki_adapter.generate_runtime_config(tenants=tenants, default_retention_days=default_ret)
        loki_adapter.write_runtime_config(content)
        results["loki"]["runtime_config_written"] = RUNTIME_CONFIG_PATH
        if LOKI_ADMIN_URL:
            ok, detail = loki_adapter.reload_runtime_config()
            results["loki"]["reload"] = {"ok": ok, "detail": detail}
    except Exception as e:
        results["loki"]["error"] = str(e)

    # Apply Elasticsearch ILM
    elastic_cfg = cfg.get("elastic", {})
    policies = elastic_cfg.get("policies", [])
    applied = []
    errors = []
    for p in policies:
        try:
            elastic_adapter.ensure_ilm_policy(
                name=p["name"],
                hot_days=p.get("hot_days"),
                warm_days=p.get("warm_days"),
                delete_after_days=p.get("delete_after_days"),
            )
            pattern = p.get("index_pattern")
            if pattern:
                elastic_adapter.ensure_index_template(pattern, p["name"], template_name=f"tpl-{p['name']}")
            applied.append(p["name"])
        except Exception as e:
            errors.append({"policy": p.get("name"), "error": str(e)})
    results["elastic"]["applied"] = applied
    if errors:
        results["elastic"]["errors"] = errors

    return jsonify(results)


@app.route("/generate/loki-config", methods=["GET"]) 
def generate_loki_config():
    cfg = policy_service.load()
    loki_cfg = cfg.get("loki", {})
    enable_retention = True
    text = loki_adapter.generate_base_config(enable_retention=enable_retention)
    return app.response_class(response=text, status=200, mimetype="text/plain")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))



def create_app():
    return app


@app.route('/api/retention-policies', methods=['GET'])
def _auto_stub_api_retention_policies():
    return 'Auto-generated stub for /api/retention-policies', 200


@app.route('/api/retention-policies/loki', methods=['GET', 'PUT'])
def _auto_stub_api_retention_policies_loki():
    return 'Auto-generated stub for /api/retention-policies/loki', 200


@app.route('/api/logs/ingest', methods=['POST'])
def _auto_stub_api_logs_ingest():
    return 'Auto-generated stub for /api/logs/ingest', 200


@app.route('/api/logs/cleanup', methods=['POST'])
def _auto_stub_api_logs_cleanup():
    return 'Auto-generated stub for /api/logs/cleanup', 200
