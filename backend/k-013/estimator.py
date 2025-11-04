from typing import Dict, Any
import math

# Very rough token estimate: tokens ~ words * 1.3; words ~ whitespace splits
# This provides a consistent heuristic without external dependencies.
def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    words = len(text.strip().split())
    tokens = int(math.ceil(words * 1.3))
    # Clamp to at least words to avoid 0 when single char
    return max(tokens, words)


def derive_required_quality(input_text: str, constraints: Dict[str, Any], metadata: Dict[str, Any]) -> int:
    # Priority: explicit min_quality in constraints
    if isinstance(constraints.get("min_quality"), int):
        return max(1, min(5, constraints["min_quality"]))

    task_type = (metadata.get("task_type") or "generic").lower()
    base = 3
    if task_type in ("code", "math", "logic"):
        base = 5
    elif task_type in ("analysis", "reasoning", "qa"):
        base = 4
    elif task_type in ("summarization", "extract", "classify"):
        base = 2

    # Complexity bump based on size
    n_chars = len(input_text or "")
    expected_out = estimate_expected_output_tokens(input_text, metadata)
    if n_chars > 2000 or expected_out > 600:
        base = min(5, base + 1)

    return max(1, min(5, base))


def estimate_expected_output_tokens(input_text: str, metadata: Dict[str, Any]) -> int:
    # If user provides an explicit expected output tokens, honor it
    exp = metadata.get("expected_output_tokens")
    if isinstance(exp, int) and exp > 0:
        return exp

    in_tokens = estimate_tokens(input_text)
    task_type = (metadata.get("task_type") or "generic").lower()

    # Heuristic ratios by task
    ratios = {
        "summarization": 0.5,
        "extract": 0.3,
        "classify": 0.2,
        "qa": 0.7,
        "analysis": 1.0,
        "code": 1.2,
    }
    ratio = ratios.get(task_type, 0.8)
    out = int(math.ceil(in_tokens * ratio))

    # Clamp reasonable bounds
    out = max(32, min(out, 1500))
    return out

