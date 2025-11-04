import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional
from metrics.implementations import compute_all_metrics, compute_score, DEFAULT_WEIGHTS

class AgentCompetitionManager:
    def __init__(self, strategies_registry: Dict[str, object]):
        self.strategies_registry = strategies_registry

    def compete(
        self,
        prompt: str,
        strategy_names: Optional[List[str]] = None,
        weights: Optional[Dict[str, float]] = None,
        keywords: Optional[List[str]] = None,
        target_length: Optional[object] = None,
        timeout: float = 5.0,
        strategy_timeout: float = 3.0,
        top_k: int = 3,
    ) -> Dict:
        if strategy_names:
            selected = {name: self.strategies_registry[name] for name in strategy_names if name in self.strategies_registry}
        else:
            selected = self.strategies_registry

        if not selected:
            return {
                "error": "No valid strategies selected.",
                "strategies_available": list(self.strategies_registry.keys()),
            }

        weights = (weights or DEFAULT_WEIGHTS).copy()

        # Runner function for a single strategy
        def run_strategy(name, strategy):
            start = time.time()
            output = strategy.run(prompt=prompt, config={
                "keywords": keywords,
                "target_length": target_length,
                "strategy_timeout": strategy_timeout,
            })
            elapsed = time.time() - start
            metrics = compute_all_metrics(
                output=output,
                prompt=prompt,
                elapsed_sec=elapsed,
                config={
                    "keywords": keywords,
                    "target_length": target_length,
                    "strategy_timeout": strategy_timeout,
                },
            )
            score = compute_score(metrics, weights)
            return {
                "strategy": name,
                "output": output,
                "metrics": metrics,
                "score": score,
                "elapsed_sec": round(elapsed, 6),
            }

        futures = []
        results = []
        timed_out = []
        errors = []

        deadline = time.time() + max(timeout, 0.001)

        with ThreadPoolExecutor(max_workers=max(1, len(selected))) as executor:
            for name, strategy in selected.items():
                futures.append((name, executor.submit(run_strategy, name, strategy)))

            for name, future in futures:
                remaining_overall = max(0.0, deadline - time.time())
                per_future_timeout = min(strategy_timeout, remaining_overall) if strategy_timeout else remaining_overall
                if per_future_timeout <= 0:
                    timed_out.append(name)
                    continue
                try:
                    res = future.result(timeout=per_future_timeout)
                    results.append(res)
                except Exception as e:
                    # Distinguish timeout vs other errors based on message
                    msg = str(e)
                    if "timeout" in msg.lower() or "timed out" in msg.lower():
                        timed_out.append(name)
                    else:
                        errors.append({"strategy": name, "error": msg})

        # Sort by score desc
        results_sorted = sorted(results, key=lambda r: r.get("score", 0.0), reverse=True)
        best = results_sorted[0] if results_sorted else None

        response = {
            "prompt": prompt,
            "strategies_run": [name for name, _ in futures],
            "used_weights": weights,
            "timed_out": timed_out,
            "errors": errors,
            "all": results_sorted,
            "top": results_sorted[:max(1, int(top_k))],
        }
        if best:
            response["best"] = best
        else:
            response["best"] = None
        return response

