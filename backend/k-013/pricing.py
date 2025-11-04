from router import ModelSpec

def estimate_cost(spec: ModelSpec, input_tokens: int, output_tokens: int) -> float:
    in_cost = (input_tokens / 1000.0) * spec.input_cost_per_1k
    out_cost = (output_tokens / 1000.0) * spec.output_cost_per_1k
    return round(in_cost + out_cost, 8)

