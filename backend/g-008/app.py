import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import time
from flask import Flask, request, jsonify
from config import Config
from router.router import HybridRouter
from router.policy import PolicyEngine, RequestContext

app = Flask(__name__)
config = Config()
policy_engine = PolicyEngine(config)
router = HybridRouter(config)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

@app.route('/generate', methods=['POST'])
def generate():
    started = time.time()
    data = request.get_json(force=True, silent=True) or {}

    prompt = data.get('prompt', '')
    if not prompt:
        return jsonify({"error": "Missing 'prompt' in request body"}), 400

    ctx = RequestContext(
        user_id=data.get('user_id'),
        prompt=prompt,
        model_preference=data.get('model_preference'),  # 'local' | 'openai' | None
        hints=(data.get('hints') or {}),  # { latency, cost_sensitivity, safety_level }
        max_tokens=data.get('max_tokens'),
        temperature=data.get('temperature'),
        remote_model=data.get('model')
    )

    decision = policy_engine.decide(ctx)

    try:
        exec_result = router.route_and_execute(ctx, decision)
    except Exception as e:
        return jsonify({
            "error": str(e),
            "provider": decision.provider,
            "reason": decision.reason
        }), 500

    total_ms = int((time.time() - started) * 1000)
    resp = {
        "provider": decision.provider,
        "model": exec_result.get('model'),
        "reason": decision.reason,
        "output": exec_result.get('output'),
        "usage": exec_result.get('usage'),
        "latency_ms": exec_result.get('latency_ms'),
        "end_to_end_latency_ms": total_ms,
        "policy": {
            "rules_applied": decision.rules_applied,
            "constraints": decision.constraints
        }
    }
    return jsonify(resp)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '8000')), debug=os.getenv('FLASK_DEBUG', '0') == '1')



def create_app():
    return app


@app.route('/predict', methods=['POST'])
def _auto_stub_predict():
    return 'Auto-generated stub for /predict', 200


@app.route('/route-info', methods=['POST'])
def _auto_stub_route_info():
    return 'Auto-generated stub for /route-info', 200
