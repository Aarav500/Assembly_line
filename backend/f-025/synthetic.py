import random
from typing import Dict, Tuple


def generate_baseline(
    num_metrics: int = 50,
    seed: int | None = None,
    mean_range: Tuple[float, float] = (50.0, 100.0),
    std_range: Tuple[float, float] = (1.0, 5.0),
    metric_prefix: str = "metric",
) -> dict:
    rng = random.Random(seed)
    lo_m, hi_m = mean_range
    lo_s, hi_s = std_range

    metrics: Dict[str, dict] = {}
    for i in range(1, num_metrics + 1):
        name = f"{metric_prefix}_{i}"
        mu = rng.uniform(lo_m, hi_m)
        sigma = rng.uniform(lo_s, hi_s)
        val = rng.gauss(mu, sigma)
        metrics[name] = {
            "mean": mu,
            "std": sigma,
            "baseline_value": val,
        }

    return {"metrics": metrics}


def generate_run_metrics(
    baseline: dict,
    drift: dict | None = None,
    seed: int | None = None,
) -> Dict[str, float]:
    if drift is None:
        drift = {}

    rng = random.Random(seed)

    mean_shift = float(drift.get("mean_shift", 0.0))
    std_scale = float(drift.get("std_scale", 1.0))
    regress_fraction = float(drift.get("regress_fraction", 0.0))
    regress_strength = float(drift.get("regress_strength", 2.5))  # in sigmas
    direction = drift.get("direction", "mix")  # "up", "down", or "mix"

    metrics = {}
    names = list(baseline.get("metrics", {}).keys())

    # sample nominal values
    for name, info in baseline.get("metrics", {}).items():
        mu = float(info.get("mean", 0.0)) + mean_shift
        sigma = max(float(info.get("std", 1.0)) * std_scale, 1e-12)
        v = rng.gauss(mu, sigma)
        metrics[name] = v

    # apply regressions to a subset
    n = len(names)
    k = int(max(0, min(n, round(regress_fraction * n))))
    if k > 0 and n > 0 and regress_strength != 0:
        chosen = rng.sample(names, k)
        for name in chosen:
            info = baseline["metrics"][name]
            sigma = max(float(info.get("std", 1.0)) * std_scale, 1e-12)
            # shift by multiple of sigma
            if direction == "up":
                sgn = 1.0
            elif direction == "down":
                sgn = -1.0
            else:
                sgn = 1.0 if rng.random() < 0.5 else -1.0
            metrics[name] += sgn * regress_strength * sigma

    return metrics

