import os
from flask import Flask, request, jsonify
from router import Router
from config import load_model_registry

app = Flask(__name__)

# Build registry and router once at startup
model_registry = load_model_registry()
router = Router(model_registry=model_registry)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/models", methods=["GET"])
def list_models():
    models = []
    for key, spec in model_registry.items():
        models.append({
            "key": key,
            "provider": spec.provider,
            "name": spec.name,
            "quality": spec.quality,
            "input_cost_per_1k": spec.input_cost_per_1k,
            "output_cost_per_1k": spec.output_cost_per_1k,
            "latency_ms": spec.latency_ms,
            "max_output_tokens": spec.max_output_tokens,
        })
    return jsonify({"models": models})

@app.route("/route", methods=["POST"])
def route_request():
    try:
        payload = request.get_json(force=True, silent=False) or {}
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    input_text = payload.get("input")
    if not input_text or not isinstance(input_text, str):
        return jsonify({"error": "Field 'input' (string) is required"}), 400

    constraints = payload.get("constraints") or {}
    metadata = payload.get("metadata") or {}
    force_model = payload.get("force_model")

    try:
        decision, generation = router.route(
            input_text=input_text,
            constraints=constraints,
            metadata=metadata,
            force_model=force_model,
        )
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": "Routing failed", "details": str(e)}), 500

    return jsonify({
        "model": decision.get("model_key"),
        "strategy": decision.get("strategy"),
        "decision_trace": decision.get("decision_trace", []),
        "estimate": decision.get("estimate"),
        "response": generation.get("output"),
        "provider_latency_ms": generation.get("latency_ms_estimate"),
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)

