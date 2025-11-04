from typing import Dict, Any, List, Tuple
import time
from .metrics import compute_metric_value
from .judge import evaluate_rule


class CanaryAnalysisEngine:
    def __init__(self, store=None) -> None:
        self.store = store

    @staticmethod
    def normalize_dataset(metrics: Dict[str, Any]) -> Dict[str, List[Any]]:
        if not isinstance(metrics, dict):
            raise ValueError("metrics must be an object")
        norm: Dict[str, List[Any]] = {}
        for name, series in metrics.items():
            if not isinstance(series, list):
                raise ValueError(f"metric '{name}' must be a list")
            norm[name] = series
        return norm

    def run_analysis(
        self,
        baseline: Dict[str, Any],
        canary: Dict[str, Any],
        rules: List[Dict[str, Any]],
        pass_threshold: float = 80.0,
    ) -> Dict[str, Any]:
        baseline_ds = baseline.get("metrics")
        canary_ds = canary.get("metrics")
        if not baseline_ds or not canary_ds:
            raise ValueError("baseline and canary must include 'metrics'")
        if not isinstance(rules, list) or len(rules) == 0:
            raise ValueError("rules must be a non-empty list")

        results = []
        total_weight = 0.0
        passed_weight = 0.0
        hard_failures = []

        for rule in rules:
            name = rule.get("name") or rule.get("id") or f"metric_{len(results)+1}"
            weight = float(rule.get("weight", 1.0))
            critical = bool(rule.get("critical", False))

            base_spec = rule.get("baseline_metric") or rule.get("metric")
            can_spec = rule.get("canary_metric") or rule.get("metric")
            if base_spec is None or can_spec is None:
                raise ValueError(f"rule '{name}' missing baseline_metric/canary_metric")

            baseline_value = compute_metric_value(baseline_ds, base_spec)
            canary_value = compute_metric_value(canary_ds, can_spec)

            eval_res = evaluate_rule(baseline_value, canary_value, rule)
            metric_passed = bool(eval_res["passed"])

            total_weight += weight
            if metric_passed:
                passed_weight += weight
            else:
                if critical:
                    hard_failures.append(name)

            results.append({
                "name": name,
                "baseline_value": baseline_value,
                "canary_value": canary_value,
                "weight": weight,
                "critical": critical,
                **eval_res,
            })

        score = 0.0 if total_weight == 0 else (passed_weight / total_weight) * 100.0
        status = "PASS" if (score >= float(pass_threshold) and len(hard_failures) == 0) else "FAIL"

        return {
            "status": status,
            "score": round(score, 4),
            "pass_threshold": float(pass_threshold),
            "hard_failures": hard_failures,
            "results": results,
            "timestamp": int(time.time()),
            "version": "1.0.0",
        }

