import json
import uuid
import requests

DATA = {
    "service": "checkout",
    "aggregate_score": 88.7,
    "thresholds": {"pass": 90, "warn": 75},
    "metrics": [
        {"name": "latency_p50_ms", "baseline": 120, "canary": 118, "score": 96.5, "status": "pass"},
        {"name": "latency_p95_ms", "baseline": 240, "canary": 255, "score": 60.0, "status": "fail"},
        {"name": "error_rate_%", "baseline": 0.35, "canary": 0.40, "score": 85.0, "status": "warn"}
    ],
    "decision": {"result": "hold", "reason": "p95 latency regression"},
    "metadata": {"build": "2.1.0", "env": "staging"}
}

if __name__ == "__main__":
    run_id = str(uuid.uuid4())
    DATA["id"] = run_id
    r = requests.post("http://localhost:5000/api/runs", json=DATA)
    print(r.status_code, r.text)
    d = requests.post(f"http://localhost:5000/api/runs/{run_id}/decision", json={"user":"qa","result":"hold","reason":"waiting for next sample"})
    print(d.status_code, d.text)

