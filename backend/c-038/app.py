import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import time
import json
import math
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any
from flask import Flask, jsonify, render_template, request, abort


# ----------------------
# Config and Store
# ----------------------

DATA_DIR = os.environ.get("OBS_DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _hash_seed(*parts: str) -> int:
    h = hashlib.sha256("::".join(parts).encode("utf-8")).hexdigest()
    return int(h[:16], 16)


class ProjectStore:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        _ensure_data_dir()
        self._projects_fp = os.path.join(self.data_dir, "projects.json")
        self._ensure_projects_file()
        self._index = None
        self._load()

    def _ensure_projects_file(self):
        if not os.path.exists(self._projects_fp):
            default = {
                "projects": [
                    {
                        "id": "payments",
                        "name": "Payments Service",
                        "description": "Handles payment processing and billing.",
                        "tags": ["critical", "backend"]
                    },
                    {
                        "id": "web",
                        "name": "Web Frontend",
                        "description": "Customer-facing web application.",
                        "tags": ["frontend"]
                    },
                    {
                        "id": "search",
                        "name": "Search API",
                        "description": "Full-text search and suggestions.",
                        "tags": ["backend", "latency-sensitive"]
                    }
                ]
            }
            with open(self._projects_fp, "w", encoding="utf-8") as f:
                json.dump(default, f, indent=2)

    def _load(self):
        with open(self._projects_fp, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._index = {p["id"]: p for p in data.get("projects", [])}

    def list_projects(self) -> List[Dict[str, Any]]:
        return list(self._index.values())

    def get_project(self, project_id: str) -> Dict[str, Any]:
        return self._index.get(project_id)


# ----------------------
# Pre-built Panels
# ----------------------

# Define a set of pre-built, auto-generated panels applicable to all projects.
# Each panel maps to a synthetic metric key for this demo implementation.
PREBUILT_PANELS = [
    {"id": "rpm", "title": "Requests per Minute", "metric": "rpm", "unit": "rpm", "type": "line", "color": "#2563eb"},
    {"id": "error_rate", "title": "Error Rate", "metric": "error_rate", "unit": "%", "type": "line", "color": "#dc2626"},
    {"id": "latency_p95", "title": "Latency P95", "metric": "latency_p95", "unit": "ms", "type": "line", "color": "#7c3aed"},
    {"id": "latency_p50", "title": "Latency P50", "metric": "latency_p50", "unit": "ms", "type": "line", "color": "#6b7280"},
    {"id": "cpu", "title": "CPU Usage", "metric": "cpu", "unit": "%", "type": "line", "color": "#059669"},
    {"id": "memory", "title": "Memory Usage", "metric": "memory", "unit": "MB", "type": "line", "color": "#f59e0b"},
    {"id": "logs", "title": "Log Volume", "metric": "logs", "unit": "lines/min", "type": "bar", "color": "#0ea5e9"},
    {"id": "uptime", "title": "Uptime", "metric": "uptime", "unit": "%", "type": "line", "color": "#16a34a"},
    {"id": "active_users", "title": "Active Users", "metric": "active_users", "unit": "users", "type": "line", "color": "#ef4444"}
]


# ----------------------
# Synthetic Metric Provider (demo)
# ----------------------

class MetricProvider:
    def __init__(self):
        pass

    def generate_timeseries(self, project_id: str, metric: str, window_minutes: int = 60, step_s: int = 60) -> Dict[str, Any]:
        now = int(time.time())
        # Align to step
        now = now - (now % step_s)
        points = []
        # A project weight to vary across projects
        proj_weight = (sum(ord(c) for c in project_id) % 10) / 10.0

        for i in range(window_minutes):
            t = now - (window_minutes - 1 - i) * step_s
            # Deterministic noise per minute and metric
            seed = _hash_seed(project_id, metric, str(t // step_s))
            v = self._metric_value(metric, t, proj_weight, seed)
            points.append({
                "t": datetime.fromtimestamp(t, tz=timezone.utc).isoformat(),
                "v": v
            })
        unit = next((p["unit"] for p in PREBUILT_PANELS if p["metric"] == metric), "")
        return {
            "project": project_id,
            "metric": metric,
            "unit": unit,
            "points": points
        }

    def _rnd(self, seed: int, a: float, b: float) -> float:
        # Simple deterministic random from seed via hash -> [a,b]
        # Using a sine transform for speed and determinism
        x = math.sin(seed % 1000000) * 10000
        fract = x - math.floor(x)
        return a + (b - a) * abs(fract)

    def _metric_value(self, metric: str, t: int, w: float, seed: int) -> float:
        # Diurnal component (period ~24h)
        day_phase = 2 * math.pi * ((t % 86400) / 86400.0)
        diurnal = (math.sin(day_phase - math.pi / 2) + 1) / 2  # 0..1
        noise = self._rnd(seed, -0.1, 0.1)

        if metric == "rpm":
            base = 80 + 120 * diurnal + 40 * w
            return max(0, round(base * (1 + noise), 2))
        elif metric == "error_rate":
            base = 0.5 + 1.5 * (1 - diurnal) + 0.5 * w
            spike = 4.0 if (t // 3600 + int(w * 10)) % 9 == 0 else 0.0
            val = base + spike + noise * 2
            return max(0.0, round(min(val, 15.0), 3))
        elif metric == "latency_p95":
            base = 250 + 150 * (1 - diurnal) + 50 * w
            jitter = self._rnd(seed, -30, 30)
            return max(0, round(base + jitter, 1))
        elif metric == "latency_p50":
            base = 80 + 60 * (1 - diurnal) + 20 * w
            jitter = self._rnd(seed, -15, 15)
            return max(0, round(base + jitter, 1))
        elif metric == "cpu":
            base = 35 + 40 * diurnal + 10 * w
            jitter = self._rnd(seed, -5, 5)
            return round(min(max(base + jitter, 0), 100), 2)
        elif metric == "memory":
            base = 400 + 300 * diurnal + 200 * w
            jitter = self._rnd(seed, -40, 60)
            return round(max(base + jitter, 0), 1)
        elif metric == "logs":
            base = 500 + 900 * diurnal + 200 * w
            jitter = self._rnd(seed, -100, 150)
            return max(0, int(base + jitter))
        elif metric == "uptime":
            # Near 100 with occasional tiny dips
            dip = 0.0
            if (t // 600 + int(w * 10)) % 97 == 0:
                dip = self._rnd(seed, 1, 6)
            val = 100.0 - dip + noise
            return round(min(max(val, 80.0), 100.0), 3)
        elif metric == "active_users":
            base = 20 + 200 * diurnal + 80 * w
            jitter = self._rnd(seed, -10, 20)
            return max(0, int(base + jitter))
        else:
            return round(self._rnd(seed, 0, 100), 2)


# ----------------------
# Flask App
# ----------------------

def create_app() -> Flask:
    app = Flask(__name__)
    store = ProjectStore(DATA_DIR)
    metrics = MetricProvider()

    @app.route("/")
    def index():
        projects = store.list_projects()
        return render_template("index.html", projects=projects)

    @app.route("/projects/<project_id>/dashboard")
    def project_dashboard(project_id: str):
        p = store.get_project(project_id)
        if not p:
            abort(404)
        return render_template("dashboard.html", project=p)

    # API endpoints
    @app.get("/api/projects")
    def api_list_projects():
        return jsonify({"projects": store.list_projects()})

    @app.get("/api/projects/<project_id>")
    def api_get_project(project_id: str):
        p = store.get_project(project_id)
        if not p:
            abort(404)
        return jsonify(p)

    @app.get("/api/projects/<project_id>/panels")
    def api_project_panels(project_id: str):
        if not store.get_project(project_id):
            abort(404)
        return jsonify({"project": project_id, "panels": PREBUILT_PANELS})

    @app.get("/api/projects/<project_id>/metrics")
    def api_project_metrics(project_id: str):
        if not store.get_project(project_id):
            abort(404)
        metric = request.args.get("metric")
        if not metric:
            return jsonify({"error": "metric is required"}), 400
        try:
            window = int(request.args.get("window", "60"))
            window = min(max(window, 5), 24 * 60)  # 5 minutes to 24h
        except ValueError:
            window = 60
        series = metrics.generate_timeseries(project_id, metric, window_minutes=window, step_s=60)
        return jsonify(series)

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)



@app.route('/health', methods=['GET'])
def _auto_stub_health():
    return 'Auto-generated stub for /health', 200
