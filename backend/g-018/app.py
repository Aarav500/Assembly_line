import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, request, jsonify
from pricing import PRICING

app = Flask(__name__)


def get_effective_gpu_rate(gpu_type: str, pricing_model: str) -> float:
    gpu_pricing = PRICING["gpu"].get(gpu_type)
    if not gpu_pricing:
        raise ValueError(f"Unsupported GPU type: {gpu_type}")
    base = gpu_pricing["on_demand"]
    if pricing_model == "on_demand":
        return base
    elif pricing_model == "spot":
        return base * (1 - gpu_pricing["spot_discount"])  # effective after discount
    elif pricing_model == "reserved":
        return base * (1 - gpu_pricing["reserved_discount"])  # effective after discount
    else:
        raise ValueError(f"Unsupported pricing model: {pricing_model}")


def compute_estimate(payload: dict) -> dict:
    # Extract and validate inputs
    gpu_type = payload.get("gpu_type")
    pricing_model = payload.get("pricing_model", "on_demand")
    gpu_count = payload.get("gpu_count")
    gpu_hours = payload.get("gpu_hours")
    memory_gb = payload.get("memory_gb")
    memory_hours = payload.get("memory_hours")

    errors = []
    if gpu_type not in PRICING["gpu"]:
        errors.append("Invalid or missing gpu_type")
    if pricing_model not in ("on_demand", "spot", "reserved"):
        errors.append("Invalid pricing_model; must be 'on_demand', 'spot', or 'reserved'")

    def as_float(name, val, min_val=0.0):
        try:
            v = float(val)
        except Exception:
            errors.append(f"{name} must be a number")
            return None
        if v < min_val:
            errors.append(f"{name} must be >= {min_val}")
        return v

    gpu_count = as_float("gpu_count", gpu_count, 0)
    gpu_hours = as_float("gpu_hours", gpu_hours, 0)
    memory_gb = as_float("memory_gb", memory_gb, 0)
    memory_hours = as_float("memory_hours", memory_hours, 0)

    if errors:
        return {"ok": False, "errors": errors}

    # Compute rates
    gpu_hourly_rate_per_gpu = get_effective_gpu_rate(gpu_type, pricing_model)
    memory_gb_hour_rate = PRICING["memory_gb_hour"]

    # Compute costs
    gpu_cost = gpu_count * gpu_hours * gpu_hourly_rate_per_gpu
    memory_cost = memory_gb * memory_hours * memory_gb_hour_rate
    total_cost = gpu_cost + memory_cost

    result = {
        "ok": True,
        "currency": PRICING.get("currency", "USD"),
        "inputs": {
            "gpu_type": gpu_type,
            "pricing_model": pricing_model,
            "gpu_count": gpu_count,
            "gpu_hours": gpu_hours,
            "memory_gb": memory_gb,
            "memory_hours": memory_hours,
        },
        "rates": {
            "gpu_hourly_rate_per_gpu": gpu_hourly_rate_per_gpu,
            "memory_gb_hour_rate": memory_gb_hour_rate,
            "gpu_hourly_rate_all_gpus": gpu_hourly_rate_per_gpu * gpu_count,
            "total_hourly_rate": gpu_hourly_rate_per_gpu * gpu_count + memory_gb_hour_rate * memory_gb,
        },
        "costs": {
            "gpu_cost": gpu_cost,
            "memory_cost": memory_cost,
            "total_cost": total_cost,
        },
        "pricing": PRICING["gpu"][gpu_type],
    }
    return result


@app.route("/")
def index():
    gpu_options = PRICING["gpu"]
    currency = PRICING.get("currency", "USD")
    return render_template("index.html", gpu_options=gpu_options, currency=currency)


@app.route("/api/pricing", methods=["GET"])
def api_pricing():
    return jsonify({"ok": True, "pricing": PRICING})


@app.route("/api/estimate", methods=["POST"])
def api_estimate():
    try:
        payload = request.get_json(force=True, silent=False) or {}
    except Exception:
        return jsonify({"ok": False, "errors": ["Invalid JSON body."]}), 400

    try:
        result = compute_estimate(payload)
    except Exception as e:
        return jsonify({"ok": False, "errors": [str(e)]}), 400

    status = 200 if result.get("ok") else 400
    return jsonify(result), status


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)



def create_app():
    return app
