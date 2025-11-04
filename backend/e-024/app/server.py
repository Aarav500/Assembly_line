import os
import requests
from flask import Flask, request, jsonify

OPA_URL = os.getenv("OPA_URL", "http://localhost:8181")
OPA_DECISION_PATH = os.getenv("OPA_DECISION_PATH", "infra/policy/deny")


class OPAClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def eval(self, data_path: str, input_data: dict):
        path = data_path.replace(".", "/")
        url = f"{self.base_url}/v1/data/{path}"
        resp = requests.post(url, json={"input": input_data}, timeout=10)
        resp.raise_for_status()
        body = resp.json()
        return body.get("result", [])


app = Flask(__name__)
opa = OPAClient(OPA_URL)


def normalize_input(payload):
    normalized = {"kubernetes": [], "terraform": {}}
    if payload is None:
        return normalized

    # Already structured
    if isinstance(payload, dict) and ("kubernetes" in payload or "terraform" in payload):
        k8s = payload.get("kubernetes")
        if k8s is not None:
            if isinstance(k8s, list):
                normalized["kubernetes"] = k8s
            else:
                normalized["kubernetes"] = [k8s]
        tf = payload.get("terraform")
        if tf is not None:
            normalized["terraform"] = tf
        return normalized

    # Kubernetes object or list
    if isinstance(payload, dict) and ("kind" in payload and "apiVersion" in payload):
        normalized["kubernetes"] = [payload]
        return normalized
    if isinstance(payload, list) and payload and isinstance(payload[0], dict) and ("kind" in payload[0] and "apiVersion" in payload[0]):
        normalized["kubernetes"] = payload
        return normalized

    # Terraform plan-like
    if isinstance(payload, dict) and ("resource_changes" in payload or "planned_values" in payload):
        normalized["terraform"] = payload
        return normalized

    return normalized


@app.route("/health", methods=["GET"])
def health():
    status = "ok"
    try:
        opa.eval(OPA_DECISION_PATH, {})
    except Exception:
        status = "degraded"
    return jsonify({"status": status})


@app.route("/validate", methods=["POST"])
def validate():
    try:
        payload = request.get_json(force=True, silent=False)
    except Exception:
        return jsonify({"error": "invalid JSON"}), 400

    input_data = normalize_input(payload)

    try:
        result = opa.eval(OPA_DECISION_PATH, input_data)
    except requests.RequestException as e:
        return jsonify({"error": f"OPA request failed: {str(e)}"}), 502

    violations = result if isinstance(result, list) else []
    return jsonify({
        "allowed": len(violations) == 0,
        "violations": violations,
        "count": len(violations)
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=True)

