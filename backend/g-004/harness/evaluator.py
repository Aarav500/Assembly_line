import random
import time
from typing import Dict, Any, List
from .scorer import get_scorer
from .utils import render_prompt, now_iso, apply_postprocess


class Evaluator:
    def evaluate_suite(self, suite: Dict[str, Any], adapter, max_items: int | None = None, shuffle: bool = False, seed: int | None = None) -> Dict[str, Any]:
        items = list(suite.get("items", []))
        if shuffle:
            rng = random.Random(seed)
            rng.shuffle(items)
        if max_items is not None:
            items = items[: int(max_items)]

        scoring_cfg = suite.get("scoring", {"type": "exact", "normalize": ["lower", "strip"]})
        scorer = get_scorer(scoring_cfg.get("type", "exact"))

        results = []
        t0 = time.time()
        for idx, item in enumerate(items, start=1):
            prompt = render_prompt(item.get("prompt") or suite.get("prompt_template") or "{{input}}", {"input": item.get("input", ""), **item})
            params = suite.get("model_params") or {}
            pred = adapter.generate(prompt, item=item, params=params)
            pred = apply_postprocess(pred, suite.get("postprocess_prediction"))
            expected = item.get("expected")
            score = float(scorer(expected, pred, scoring_cfg))
            passed = bool(score >= float(scoring_cfg.get("pass_threshold", 1.0)))
            results.append({
                "index": idx,
                "id": item.get("id", str(idx)),
                "input": item.get("input"),
                "prompt": prompt,
                "expected": expected,
                "prediction": pred,
                "score": score,
                "passed": passed,
                "meta": item.get("meta", {}),
            })

        duration = time.time() - t0
        accuracy = sum(1 for r in results if r["passed"]) / len(results) if results else 0.0
        avg_score = sum(r["score"] for r in results) / len(results) if results else 0.0

        return {
            "suite": suite.get("name"),
            "task_type": suite.get("task_type", ""),
            "model": adapter.name,
            "started_at": now_iso(),
            "duration_sec": duration,
            "num_items": len(results),
            "metrics": {
                "accuracy": accuracy,
                "avg_score": avg_score,
            },
            "results": results,
        }

