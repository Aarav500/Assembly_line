import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request, render_template, Response, stream_with_context
import time
import hashlib
import json
import math
import itertools

app = Flask(__name__)

# Mock model catalog
MODELS = [
    {
        "id": "gpt-4o-mini",
        "name": "GPT-4o Mini (mock)",
        "provider": "OpenAI (mock)",
        "modalities": ["text", "image"],
        "context_length": 128000,
        "family": "gpt4o",
        "capabilities": {"streaming": True, "embeddings": True, "chat": True}
    },
    {
        "id": "llama-3.1-8b-instruct",
        "name": "Llama 3.1 8B Instruct (mock)",
        "provider": "Meta (mock)",
        "modalities": ["text"],
        "context_length": 8192,
        "family": "llama3",
        "capabilities": {"streaming": True, "embeddings": True, "chat": True}
    },
    {
        "id": "mixtral-8x7b",
        "name": "Mixtral 8x7B (mock)",
        "provider": "Mistral (mock)",
        "modalities": ["text"],
        "context_length": 65536,
        "family": "mixtral",
        "capabilities": {"streaming": True, "embeddings": True, "chat": True}
    }
]

# ------------------ Utilities ------------------

def tokenize(text: str):
    return [t for t in text.strip().split() if t]


def stable_seed(*parts) -> int:
    h = hashlib.sha256()
    for p in parts:
        if isinstance(p, (dict, list)):
            p = json.dumps(p, sort_keys=True)
        if not isinstance(p, (bytes, bytearray)):
            p = str(p).encode("utf-8", errors="ignore")
        h.update(p)
    return int(h.hexdigest(), 16) % (2**31 - 1)


def prng(seed):
    # simple LCG for deterministic pseudo-random numbers in [0,1)
    a = 1103515245
    c = 12345
    m = 2**31
    state = (seed % m)
    while True:
        state = (a * state + c) % m
        yield state / m


PHRASES = [
    "Certainly.",
    "Here's a concise answer:",
    "In short:",
    "Key points:",
    "Additionally, consider:",
    "Summary:",
    "Practical steps:",
    "Notes:",
    "Finally:",
]

FILLERS = [
    "This is a mocked response for demonstration purposes.",
    "Results will vary with real models and providers.",
    "Latencies and token counts are simulated.",
    "You can tweak temperature and max tokens to see changes.",
    "Streaming chunks emulate incremental generation.",
    "Use the embeddings tab to see vector outputs.",
]


def build_mock_text(prompt: str, model_id: str, max_tokens: int = 128, temperature: float = 0.7):
    seed = stable_seed(prompt, model_id, max_tokens, round(temperature, 2))
    rng = prng(seed)
    # Choose some phrases deterministically
    chosen = []
    for i in range(3):
        idx = int(next(rng) * len(PHRASES))
        chosen.append(PHRASES[idx])
    fill = []
    for i in range(5):
        idx = int(next(rng) * len(FILLERS))
        fill.append(FILLERS[idx])
    base = (
        f"Model {model_id} (mock) responding to your prompt. "
        f"Temperature={temperature}, Max tokens={max_tokens}. "
    )
    body = " ".join(chosen + [f"Prompt echo: {prompt.strip()}" ] + fill)
    words = tokenize(base + " " + body)
    return " ".join(words[: max_tokens or len(words)])


def estimate_tokens(text: str) -> int:
    # Rough heuristic: 1 token ~ 0.75 words
    words = len(tokenize(text))
    return max(1, int(math.ceil(words / 0.75)))


def sse_format(data: dict | str):
    if isinstance(data, dict):
        payload = json.dumps(data, ensure_ascii=False)
    else:
        payload = str(data)
    return f"data: {payload}\n\n"


def sleep_ms(ms):
    time.sleep(ms / 1000.0)


# ------------------ Routes ------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/health")
def health():
    return jsonify({"ok": True, "status": "healthy", "time": time.time()})


@app.route("/api/models")
def list_models():
    return jsonify({"data": MODELS})


@app.route("/api/endpoints")
def list_endpoints():
    return jsonify({
        "endpoints": [
            {
                "path": "/api/generate",
                "method": "POST",
                "description": "Mocked text generation (optionally streaming)",
                "sample_request": {
                    "model": "gpt-4o-mini",
                    "prompt": "Explain moon phases in 2 lines.",
                    "temperature": 0.4,
                    "max_tokens": 64,
                    "stream": False
                }
            },
            {
                "path": "/api/chat",
                "method": "POST",
                "description": "Mocked chat completion",
                "sample_request": {
                    "model": "llama-3.1-8b-instruct",
                    "messages": [
                        {"role": "user", "content": "What's the capital of Japan?"}
                    ],
                    "temperature": 0.2,
                    "max_tokens": 60,
                    "stream": True
                }
            },
            {
                "path": "/api/embeddings",
                "method": "POST",
                "description": "Mocked embeddings generation",
                "sample_request": {
                    "model": "mixtral-8x7b",
                    "input": "A quick brown fox jumps over the lazy dog.",
                    "dimension": 128
                }
            }
        ]
    })


@app.route("/api/generate", methods=["POST"])
def generate():
    data = request.get_json(force=True, silent=True) or {}
    model = data.get("model") or MODELS[0]["id"]
    prompt = (data.get("prompt") or "").strip()
    temperature = float(data.get("temperature", 0.7))
    max_tokens = int(data.get("max_tokens", 128))
    stream = bool(data.get("stream", False))

    if not prompt:
        return jsonify({"error": {"type": "invalid_request", "message": "prompt is required"}}), 400

    completion = build_mock_text(prompt, model, max_tokens, temperature)
    prompt_tokens = estimate_tokens(prompt)
    completion_tokens = estimate_tokens(completion)

    # Simulate latency based on prompt length
    base_latency_ms = min(1200, 100 + len(prompt) * 10)

    if not stream:
        sleep_ms(base_latency_ms)
        return jsonify({
            "model": model,
            "object": "text.completion",
            "created": int(time.time()),
            "output": completion,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            }
        })

    @stream_with_context
    def gen():
        # Send chunks word-by-word
        words = completion.split()
        t0 = time.time()
        # Initial event
        yield sse_format({"event": "start", "model": model, "created": int(t0)})
        sleep_ms(150 + base_latency_ms // 4)
        for i, w in enumerate(words):
            yield sse_format({"event": "chunk", "index": i, "text": w + (" " if i < len(words) - 1 else "")})
            sleep_ms(18 + (i % 5))
        usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }
        yield sse_format({"event": "end", "usage": usage})
        yield sse_format("[DONE]")

    headers = {
        "Cache-Control": "no-cache",
        "Content-Type": "text/event-stream",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return Response(gen(), headers=headers)


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True, silent=True) or {}
    model = data.get("model") or MODELS[0]["id"]
    messages = data.get("messages") or []
    temperature = float(data.get("temperature", 0.7))
    max_tokens = int(data.get("max_tokens", 128))
    stream = bool(data.get("stream", False))

    if not messages or not isinstance(messages, list):
        return jsonify({"error": {"type": "invalid_request", "message": "messages array is required"}}), 400

    last_user = next((m for m in reversed(messages) if m.get("role") == "user"), None)
    user_text = (last_user.get("content") if last_user else "").strip()

    if not user_text:
        user_text = "Hello!"

    reply = build_mock_text(user_text, model, max_tokens, temperature)

    prompt_tokens = sum(estimate_tokens(m.get("content", "")) for m in messages)
    completion_tokens = estimate_tokens(reply)

    if not stream:
        sleep_ms(min(900, 100 + prompt_tokens))
        return jsonify({
            "model": model,
            "object": "chat.completion",
            "created": int(time.time()),
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": reply},
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            }
        })

    @stream_with_context
    def gen():
        words = reply.split()
        yield sse_format({"event": "start", "model": model, "created": int(time.time())})
        sleep_ms(200)
        for i, w in enumerate(words):
            delta = {"role": "assistant", "content": w + (" " if i < len(words) - 1 else "")}
            yield sse_format({"event": "delta", "index": 0, "delta": delta})
            sleep_ms(20 + (i % 7))
        usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }
        yield sse_format({"event": "end", "usage": usage})
        yield sse_format("[DONE]")

    headers = {
        "Cache-Control": "no-cache",
        "Content-Type": "text/event-stream",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return Response(gen(), headers=headers)


@app.route("/api/embeddings", methods=["POST"])
def embeddings():
    data = request.get_json(force=True, silent=True) or {}
    model = data.get("model") or MODELS[0]["id"]
    text = (data.get("input") or "").strip()
    dim = int(data.get("dimension", 128))
    if not text:
        return jsonify({"error": {"type": "invalid_request", "message": "input is required"}}), 400
    dim = max(8, min(2048, dim))

    seed = stable_seed(model, text, dim)
    r = prng(seed)
    vec = []
    for i in range(dim):
        # map [0,1) -> [-1, 1)
        v = next(r) * 2.0 - 1.0
        vec.append(round(v, 6))

    sleep_ms(min(500, 50 + len(text)))

    return jsonify({
        "model": model,
        "object": "embedding",
        "embedding": vec,
        "dimension": dim,
        "usage": {
            "prompt_tokens": estimate_tokens(text),
            "total_tokens": estimate_tokens(text),
        }
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)



def create_app():
    return app
