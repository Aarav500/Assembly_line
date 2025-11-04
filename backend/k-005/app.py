import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import time
from flask import Flask, request, jsonify
from config import Config
from batching import BatchManager
from cache import ResponseCache
from token_opt import TokenOptimizer
from utils import compute_request_hash, normalize_openai_response

app = Flask(__name__)
config = Config.from_env()
cache = ResponseCache(ttl_seconds=config.CACHE_TTL_SEC, max_entries=config.CACHE_MAX_ENTRIES)
batch_manager = BatchManager(config=config, cache=cache)
optimizer = TokenOptimizer(config=config)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "time": int(time.time())})

@app.route("/v1/chat/completions", methods=["POST"])  # OpenAI-compatible minimal endpoint
def chat_completions():
    try:
        payload = request.get_json(force=True, silent=False) or {}
    except Exception:
        return jsonify({"error": {"message": "Invalid JSON"}}), 400

    messages = payload.get("messages")
    model = payload.get("model", config.DEFAULT_MODEL)
    temperature = payload.get("temperature", config.DEFAULT_TEMPERATURE)
    top_p = payload.get("top_p", config.DEFAULT_TOP_P)
    max_tokens = payload.get("max_tokens", config.DEFAULT_MAX_OUTPUT_TOKENS)

    if not isinstance(messages, list) or not messages:
        return jsonify({"error": {"message": "messages must be a non-empty list"}}), 400

    # Preprocess and optimize
    trimmed_messages = optimizer.prepare_messages(messages, model=model, requested_output_tokens=max_tokens)

    # Cache lookup
    cache_key = compute_request_hash({
        "provider": config.DOWNSTREAM_PROVIDER,
        "model": model,
        "temperature": temperature,
        "top_p": top_p,
        "messages": trimmed_messages,
        "max_tokens": max_tokens,
    })

    cached = cache.get(cache_key)
    if cached is not None:
        return jsonify(cached)

    try:
        # Enqueue for auto-batching
        result = batch_manager.enqueue_and_wait(
            messages=trimmed_messages,
            model=model,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            cache_key=cache_key,
            timeout_seconds=config.REQUEST_TIMEOUT_SEC,
        )
        # Normalize minimal OpenAI format
        normalized = normalize_openai_response(result, model=model)
        cache.set(cache_key, normalized)
        return jsonify(normalized)
    except TimeoutError:
        return jsonify({"error": {"message": "Request timed out in batching middleware"}}), 504
    except Exception as e:
        return jsonify({"error": {"message": str(e)}}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")), debug=bool(int(os.getenv("DEBUG", "0"))))



def create_app():
    return app


@app.route('/batch', methods=['POST'])
def _auto_stub_batch():
    return 'Auto-generated stub for /batch', 200


@app.route('/stats', methods=['GET'])
def _auto_stub_stats():
    return 'Auto-generated stub for /stats', 200
