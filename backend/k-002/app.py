import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
from flask import Flask, request, jsonify
from agent_manager import AgentCompetitionManager
from strategies.implementations import build_strategies_registry
from metrics.implementations import DEFAULT_WEIGHTS, AVAILABLE_METRICS

app = Flask(__name__)

strategies_registry = build_strategies_registry()
manager = AgentCompetitionManager(strategies_registry)

@app.route("/health", methods=["GET"]) 
def health():
    return jsonify({"status": "ok"})

@app.route("/strategies", methods=["GET"]) 
def strategies():
    items = []
    for name, strategy in strategies_registry.items():
        items.append({
            "name": name,
            "description": getattr(strategy, "description", "")
        })
    return jsonify({"strategies": items})

@app.route("/metrics", methods=["GET"]) 
def metrics():
    return jsonify({
        "metrics": AVAILABLE_METRICS,
        "default_weights": DEFAULT_WEIGHTS
    })

@app.route("/compete", methods=["POST"]) 
def compete():
    payload = request.get_json(force=True, silent=True) or {}
    prompt = payload.get("prompt")
    if not prompt or not isinstance(prompt, str):
        return jsonify({"error": "Field 'prompt' (string) is required."}), 400

    strategy_names = payload.get("strategies")
    weights = payload.get("weights") or DEFAULT_WEIGHTS.copy()
    keywords = payload.get("keywords")
    target_length = payload.get("target_length")
    timeout = payload.get("timeout", 5.0)
    strategy_timeout = payload.get("strategy_timeout", 3.0)
    top_k = payload.get("top_k", 3)

    start = time.time()

    result = manager.compete(
        prompt=prompt,
        strategy_names=strategy_names,
        weights=weights,
        keywords=keywords,
        target_length=target_length,
        timeout=timeout,
        strategy_timeout=strategy_timeout,
        top_k=top_k,
    )

    result["elapsed_total_sec"] = round(time.time() - start, 6)

    return jsonify(result)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)



def create_app():
    return app
