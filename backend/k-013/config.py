import os
import json
from typing import Dict, List
from router import ModelSpec

DEFAULT_MODELS = [
    # provider, name, quality, input_cost_per_1k, output_cost_per_1k, latency_ms, max_output_tokens
    ("mock", "basic", 2, 0.0002, 0.0004, 200, 1024),
    ("mock", "advanced", 4, 0.0020, 0.0060, 500, 2048),
    ("mock", "ultra", 5, 0.0100, 0.0120, 1200, 4096),
]


def _models_from_list(items: List[list]) -> Dict[str, ModelSpec]:
    registry: Dict[str, ModelSpec] = {}
    for tup in items:
        provider, name, quality, in_cost, out_cost, latency, max_out = tup
        spec = ModelSpec(
            provider=provider,
            name=name,
            quality=int(quality),
            input_cost_per_1k=float(in_cost),
            output_cost_per_1k=float(out_cost),
            latency_ms=int(latency),
            max_output_tokens=int(max_out),
        )
        registry[spec.key] = spec
    return registry


def load_model_registry() -> Dict[str, ModelSpec]:
    # Allow environment-provided JSON to override defaults.
    # Expected format: [[provider, name, quality, in_cost, out_cost, latency_ms, max_output_tokens], ...]
    raw = os.environ.get("MODELS_CONFIG_JSON")
    if raw:
        try:
            items = json.loads(raw)
            return _models_from_list(items)
        except Exception as e:
            raise ValueError(f"Invalid MODELS_CONFIG_JSON: {e}")

    # Optionally append an OpenAI model if explicitly configured
    extra = []
    openai_model = os.environ.get("OPENAI_MODEL_NAME")
    if openai_model:
        # Pricing can be provided via env, defaults are placeholders
        in_cost = float(os.environ.get("OPENAI_INPUT_COST_PER_1K", "0.005"))
        out_cost = float(os.environ.get("OPENAI_OUTPUT_COST_PER_1K", "0.015"))
        quality = int(os.environ.get("OPENAI_MODEL_QUALITY", "4"))
        latency = int(os.environ.get("OPENAI_MODEL_LATENCY_MS", "700"))
        max_out = int(os.environ.get("OPENAI_MODEL_MAX_TOKENS", "4096"))
        extra.append(("openai", openai_model, quality, in_cost, out_cost, latency, max_out))

    return _models_from_list(DEFAULT_MODELS + extra)

