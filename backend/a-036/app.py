import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import date, datetime, timedelta
import math
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)


def parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        return None


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def noise_from_seed(seed: int, scale: float) -> float:
    # Simple deterministic pseudo-noise based on sine
    return math.sin(seed * 0.0174533) * scale  # radians conversion for variety


def generate_trend_data(start: date, end: date):
    if end < start:
        raise ValueError("end date must be >= start date")

    days = (end - start).days + 1
    points = []

    for i in range(days):
        d = start + timedelta(days=i)
        # Create a stable integer seed based on date for deterministic noise
        seed_base = int(d.strftime("%Y%m%d"))

        # Complexity: gradual decrease over time with small noise
        complexity_trend = 70 - 0.25 * i
        complexity = complexity_trend + noise_from_seed(seed_base * 31 + 7, 4.0)
        complexity = clamp(complexity, 5, 100)

        # Dependencies: gradual increase over time with small noise
        dependencies_trend = 5 + 0.2 * i
        dependencies = dependencies_trend + noise_from_seed(seed_base * 17 + 11, 1.2)
        dependencies = clamp(dependencies, 0, 100)

        # Readiness: S-curve (sigmoid) progression across the range with minor noise
        # Center sigmoid around ~45% of the timeline to show acceleration then plateau
        x = (i - days * 0.45) / 6.0
        readiness = 100.0 * (1.0 / (1.0 + math.exp(-x)))
        readiness += noise_from_seed(seed_base * 13 + 3, 2.0)
        # Slightly penalize readiness when complexity and dependencies are high
        penalty = 0.08 * max(0, complexity - 50) + 0.15 * max(0, dependencies - 20)
        readiness = clamp(readiness - penalty, 0, 100)

        points.append({
            "date": d.isoformat(),
            "complexity": round(complexity, 2),
            "dependencies": round(dependencies, 2),
            "readiness": round(readiness, 2),
        })

    return points


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/trends")
def api_trends():
    # Query parameters: start=YYYY-MM-DD, end=YYYY-MM-DD, days=N
    start_param = request.args.get("start")
    end_param = request.args.get("end")
    days_param = request.args.get("days")

    today = date.today()

    if start_param and end_param:
        start = parse_date(start_param)
        end = parse_date(end_param)
        if not start or not end:
            return jsonify({"error": "invalid date format, expected YYYY-MM-DD"}), 400
    else:
        try:
            days = int(days_param) if days_param else 60
            if days <= 0 or days > 3650:
                raise ValueError()
        except Exception:
            return jsonify({"error": "invalid days parameter"}), 400
        end = today
        start = end - timedelta(days=days - 1)

    try:
        data_points = generate_trend_data(start, end)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    # Prepare series format for charting
    complexity_series = [{"x": p["date"], "y": p["complexity"]} for p in data_points]
    dependencies_series = [{"x": p["date"], "y": p["dependencies"]} for p in data_points]
    readiness_series = [{"x": p["date"], "y": p["readiness"]} for p in data_points]

    avg_complexity = round(sum(p["complexity"] for p in data_points) / len(data_points), 2) if data_points else 0
    avg_dependencies = round(sum(p["dependencies"] for p in data_points) / len(data_points), 2) if data_points else 0
    avg_readiness = round(sum(p["readiness"] for p in data_points) / len(data_points), 2) if data_points else 0

    return jsonify({
        "summary": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "points": len(data_points),
            "averages": {
                "complexity": avg_complexity,
                "dependencies": avg_dependencies,
                "readiness": avg_readiness
            }
        },
        "series": [
            {"name": "complexity", "data": complexity_series},
            {"name": "dependencies", "data": dependencies_series},
            {"name": "readiness", "data": readiness_series}
        ]
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)



def create_app():
    return app
