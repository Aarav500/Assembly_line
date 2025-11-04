from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List

TOKEN_PER_CHAR = Decimal("0.25")  # approx 4 chars per token
TOKEN_PER_WORD = Decimal("1.3")    # rough heuristic


def _to_decimal(x):
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x))


def estimate_tokens(spec: Dict[str, Any]) -> int:
    """
    Estimate tokens from one of: tokens, chars, words.
    Priority: tokens > chars > words. Rounds to nearest integer.
    """
    if spec is None:
        return 0
    if isinstance(spec, (int, float, Decimal)):
        # allow bare number interpreted as tokens
        return int(_to_decimal(spec).to_integral_value(rounding=ROUND_HALF_UP))

    if not isinstance(spec, dict):
        raise ValueError("input/output must be a number (tokens) or an object with tokens|chars|words")

    if "tokens" in spec and spec["tokens"] is not None:
        return int(_to_decimal(spec["tokens"]).to_integral_value(rounding=ROUND_HALF_UP))
    if "chars" in spec and spec["chars"] is not None:
        val = _to_decimal(spec["chars"]) * TOKEN_PER_CHAR
        return int(val.to_integral_value(rounding=ROUND_HALF_UP))
    if "words" in spec and spec["words"] is not None:
        val = _to_decimal(spec["words"]) * TOKEN_PER_WORD
        return int(val.to_integral_value(rounding=ROUND_HALF_UP))

    return 0


def _ensure_positive_int(name: str, value: Any) -> int:
    try:
        iv = int(value)
        if iv < 0:
            raise ValueError
        return iv
    except Exception:
        raise ValueError(f"{name} must be a non-negative integer")


def compute_forecast(catalog, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Payload must be a JSON object")

    project = payload.get("project") or "default"

    assumptions = payload.get("assumptions") or {}
    overhead_tokens_per_call = _ensure_positive_int("assumptions.overhead_tokens_per_call", assumptions.get("overhead_tokens_per_call", 0))

    runs: List[Dict[str, Any]] = payload.get("runs") or []
    if not runs:
        raise ValueError("runs must be a non-empty array")

    per_model_summary: Dict[str, Dict[str, Any]] = {}
    per_item: List[Dict[str, Any]] = []

    currencies = set()

    for idx, item in enumerate(runs):
        if not isinstance(item, dict):
            raise ValueError(f"runs[{idx}] must be an object")

        model_id = item.get("model")
        if not model_id or not isinstance(model_id, str):
            raise ValueError(f"runs[{idx}].model is required and must be a string")

        model = catalog.get(model_id)
        if model is None:
            raise ValueError(f"Unknown model '{model_id}'. Use /models to see available models.")

        count = _ensure_positive_int(f"runs[{idx}].count", item.get("count", 1))
        input_tokens_est = estimate_tokens(item.get("input"))
        output_tokens_est = estimate_tokens(item.get("output"))

        # Apply overhead to input tokens
        input_tokens_per_call = input_tokens_est + overhead_tokens_per_call
        total_input_tokens = input_tokens_per_call * count
        total_output_tokens = output_tokens_est * count

        input_cost = model.cost_for_input_tokens(total_input_tokens)
        output_cost = model.cost_for_output_tokens(total_output_tokens)
        total_cost = (input_cost + output_cost).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

        currencies.add(model.currency)

        item_result = {
            "model": model_id,
            "count": count,
            "input_tokens_per_call": input_tokens_est,
            "overhead_tokens_per_call": overhead_tokens_per_call,
            "input_tokens_total": total_input_tokens,
            "output_tokens_per_call": output_tokens_est,
            "output_tokens_total": total_output_tokens,
            "currency": model.currency,
            "cost_input": float(input_cost),
            "cost_output": float(output_cost),
            "cost_total": float(total_cost),
        }
        per_item.append(item_result)

        if model_id not in per_model_summary:
            per_model_summary[model_id] = {
                "model": model_id,
                "currency": model.currency,
                "input_tokens_total": 0,
                "output_tokens_total": 0,
                "cost_input": Decimal("0"),
                "cost_output": Decimal("0"),
            }

        agg = per_model_summary[model_id]
        agg["input_tokens_total"] += total_input_tokens
        agg["output_tokens_total"] += total_output_tokens
        agg["cost_input"] += input_cost
        agg["cost_output"] += output_cost

    # Finalize summaries
    totals = {
        "input_tokens_total": 0,
        "output_tokens_total": 0,
        "cost_input": Decimal("0"),
        "cost_output": Decimal("0"),
    }

    model_summaries: List[Dict[str, Any]] = []
    for s in per_model_summary.values():
        s_total = (s["cost_input"] + s["cost_output"]).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        model_summaries.append({
            "model": s["model"],
            "currency": s["currency"],
            "input_tokens_total": s["input_tokens_total"],
            "output_tokens_total": s["output_tokens_total"],
            "cost_input": float(s["cost_input"]),
            "cost_output": float(s["cost_output"]),
            "cost_total": float(s_total),
        })

        totals["input_tokens_total"] += s["input_tokens_total"]
        totals["output_tokens_total"] += s["output_tokens_total"]
        totals["cost_input"] += s["cost_input"]
        totals["cost_output"] += s["cost_output"]

    currency = list(currencies)[0] if len(currencies) == 1 else "mixed"

    totals_out = {
        "currency": currency,
        "input_tokens_total": totals["input_tokens_total"],
        "output_tokens_total": totals["output_tokens_total"],
        "cost_input": float(totals["cost_input"].quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)),
        "cost_output": float(totals["cost_output"].quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)),
        "cost_total": float((totals["cost_input"] + totals["cost_output"]).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)),
    }

    return {
        "project": project,
        "assumptions": {
            "overhead_tokens_per_call": overhead_tokens_per_call,
            "token_per_char": float(TOKEN_PER_CHAR),
            "token_per_word": float(TOKEN_PER_WORD),
        },
        "models": model_summaries,
        "items": per_item,
        "totals": totals_out,
    }

