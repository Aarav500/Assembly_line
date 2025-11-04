import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
from autoscaler.recommender import recommend_resources
from autoscaler.k8s import generate_hpa_yaml, generate_vpa_yaml

app = Flask(__name__)


def bad_request(message):
    return jsonify({"error": message}), 400


@app.route("/api/v1/recommend", methods=["POST"])
def recommend():
    payload = request.get_json(force=True, silent=True)
    if not payload:
        return bad_request("Invalid or missing JSON body")

    metrics = payload.get("metrics")
    if not isinstance(metrics, list) or not metrics:
        return bad_request("metrics must be a non-empty list of samples")

    workload = payload.get("workload", {})
    policy = payload.get("policy", {})
    current = payload.get("current", {})

    try:
        rec = recommend_resources(
            metrics=metrics,
            policy=policy,
            current=current,
        )
    except ValueError as e:
        return bad_request(str(e))

    response = {
        "workload": {
            "name": workload.get("name"),
            "namespace": workload.get("namespace", "default"),
            "container": workload.get("container", "app"),
        },
        "recommendations": rec,
    }

    autoscaling_target = payload.get("autoscaling_target")
    include_manifests = payload.get("includeManifests", False)

    if include_manifests and autoscaling_target:
        try:
            hpa_yaml = generate_hpa_yaml(
                name=f"{autoscaling_target.get('name')}-hpa",
                namespace=workload.get("namespace", "default"),
                target=autoscaling_target,
                min_replicas=rec["hpa"]["min_replicas"],
                max_replicas=rec["hpa"]["max_replicas"],
                cpu_target_utilization=rec["hpa"]["cpu_target_utilization_percent"],
            )
            vpa_yaml = generate_vpa_yaml(
                name=f"{autoscaling_target.get('name')}-vpa",
                namespace=workload.get("namespace", "default"),
                target=autoscaling_target,
                container_name=workload.get("container", "app"),
                min_allowed=rec["vpa"]["min_allowed"],
                max_allowed=rec["vpa"]["max_allowed"],
                update_mode=rec["vpa"].get("update_mode", "Auto"),
            )
            response["manifests"] = {
                "hpa.yaml": hpa_yaml,
                "vpa.yaml": vpa_yaml,
            }
        except Exception as e:
            return bad_request(f"Failed to generate manifests: {e}")

    return jsonify(response)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)



def create_app():
    return app


@app.route('/health', methods=['GET'])
def _auto_stub_health():
    return 'Auto-generated stub for /health', 200


@app.route('/metrics', methods=['GET', 'POST'])
def _auto_stub_metrics():
    return 'Auto-generated stub for /metrics', 200


@app.route('/hpa/recommendations?replicas=3', methods=['GET'])
def _auto_stub_hpa_recommendations_replicas_3():
    return 'Auto-generated stub for /hpa/recommendations?replicas=3', 200


@app.route('/vpa/recommendations', methods=['GET'])
def _auto_stub_vpa_recommendations():
    return 'Auto-generated stub for /vpa/recommendations', 200
