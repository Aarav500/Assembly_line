from typing import Dict, Tuple, Any, List, Optional
from dataclasses import dataclass
import time
from estimator import estimate_tokens, derive_required_quality, estimate_expected_output_tokens
from pricing import estimate_cost
from providers import get_provider

@dataclass
class ModelSpec:
    provider: str
    name: str
    quality: int  # 1..5
    input_cost_per_1k: float  # USD
    output_cost_per_1k: float  # USD
    latency_ms: int
    max_output_tokens: int

    @property
    def key(self) -> str:
        return f"{self.provider}:{self.name}"

class Router:
    def __init__(self, model_registry: Dict[str, ModelSpec]):
        if not model_registry:
            raise ValueError("Empty model registry")
        self.model_registry = model_registry

    def route(
        self,
        input_text: str,
        constraints: Dict[str, Any],
        metadata: Dict[str, Any],
        force_model: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        decision = self._decide_model(input_text, constraints, metadata, force_model)
        model_key = decision["model_key"]
        spec = self.model_registry[model_key]
        provider = get_provider(spec.provider)

        # Cap output tokens by both estimate and model max
        expected_output_tokens = decision["estimate"]["output_tokens"]
        max_output_tokens = min(expected_output_tokens, spec.max_output_tokens)

        t0 = time.time()
        output = provider.generate(prompt=input_text, model_name=spec.name, max_output_tokens=max_output_tokens)
        latency_ms_estimate = spec.latency_ms
        t1 = time.time()

        generation = {
            "output": output,
            "latency_ms_estimate": latency_ms_estimate,
            "runtime_ms": int((t1 - t0) * 1000),
        }
        return decision, generation

    def _decide_model(
        self,
        input_text: str,
        constraints: Dict[str, Any],
        metadata: Dict[str, Any],
        force_model: Optional[str] = None,
    ) -> Dict[str, Any]:
        decision_trace: List[str] = []

        # Force model short-circuit
        if force_model:
            if force_model not in self.model_registry:
                raise ValueError(f"force_model '{force_model}' is not in registry")
            spec = self.model_registry[force_model]
            in_tokens = estimate_tokens(input_text)
            out_tokens = estimate_expected_output_tokens(input_text, metadata)
            cost = estimate_cost(spec, in_tokens, out_tokens)
            decision_trace.append(f"Forced model {force_model} chosen. Estimated cost ${cost:.6f} with {in_tokens}/{out_tokens} tokens.")
            return {
                "model_key": force_model,
                "strategy": "forced",
                "decision_trace": decision_trace,
                "estimate": {
                    "input_tokens": in_tokens,
                    "output_tokens": out_tokens,
                    "cost_usd": cost,
                    "latency_ms": spec.latency_ms,
                },
            }

        # Derive requirements
        required_quality = derive_required_quality(input_text, constraints, metadata)
        max_cost = constraints.get("max_cost_usd")
        max_latency_ms = constraints.get("max_latency_ms")
        prefer_provider = constraints.get("prefer_provider")

        in_tokens = estimate_tokens(input_text)
        out_tokens = estimate_expected_output_tokens(input_text, metadata)

        candidates = []
        for key, spec in self.model_registry.items():
            # Latency filter
            if max_latency_ms is not None and spec.latency_ms > max_latency_ms:
                decision_trace.append(f"Filtered {key} by latency {spec.latency_ms}ms > {max_latency_ms}ms")
                continue
            est_cost = estimate_cost(spec, in_tokens, out_tokens)
            candidates.append((key, spec, est_cost))

        if not candidates:
            raise ValueError("No models satisfy latency constraints")

        # Apply quality filter
        quality_ok = [(k, s, c) for (k, s, c) in candidates if s.quality >= required_quality]
        if quality_ok:
            decision_trace.append(f"{len(quality_ok)}/{len(candidates)} candidates meet quality >= {required_quality}")
        else:
            decision_trace.append(
                f"No candidates meet quality >= {required_quality}. Will relax quality constraint."
            )

        def sort_key(item):
            k, s, c = item
            pref_score = 0
            if prefer_provider and s.provider == prefer_provider:
                pref_score = -0.0000001  # nudge preferred provider to be slightly cheaper in tie-breaks
            return (c + pref_score, -s.quality, s.latency_ms)

        def pick_best(pool: List):
            return sorted(pool, key=sort_key)[0]

        # Primary path: quality -> cost
        selection_reason = None
        chosen = None

        # Try meeting both quality and cost
        if quality_ok and max_cost is not None:
            qc_ok = [(k, s, c) for (k, s, c) in quality_ok if c <= max_cost]
            if qc_ok:
                chosen = pick_best(qc_ok)
                selection_reason = f"Meets quality >= {required_quality} and cost <= ${max_cost:.4f}"

        # Next: meet quality only, pick cheapest
        if chosen is None and quality_ok:
            chosen = pick_best(quality_ok)
            selection_reason = f"No model meets cost <= ${max_cost:.4f}" if max_cost is not None else "Cost unconstrained. Best among quality-qualified."

        # Next: ignore quality, meet cost if possible
        if chosen is None and max_cost is not None:
            c_ok = [(k, s, c) for (k, s, c) in candidates if c <= max_cost]
            if c_ok:
                chosen = pick_best(c_ok)
                selection_reason = f"Relaxed quality. Meets cost <= ${max_cost:.4f}"

        # Final fallback: absolute cheapest
        if chosen is None:
            chosen = pick_best(candidates)
            selection_reason = "Relaxed all constraints. Chose absolute cheapest by estimate."

        key, spec, cost = chosen
        decision_trace.append(f"Selected {key}. {selection_reason}. Estimated cost ${cost:.6f}, quality {spec.quality}, latency {spec.latency_ms}ms.")

        strategy = "quality_then_cost"
        if prefer_provider:
            strategy += "_with_provider_bias"

        return {
            "model_key": key,
            "strategy": strategy,
            "decision_trace": decision_trace,
            "estimate": {
                "input_tokens": in_tokens,
                "output_tokens": out_tokens,
                "cost_usd": cost,
                "latency_ms": spec.latency_ms,
            },
        }

