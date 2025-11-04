import re
from string import Formatter
from typing import Any, Dict


def coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "t"}
    return False


def to_probability(value: Any, default: float = 0.5) -> float:
    try:
        p = float(value)
        if p < 0:
            return 0.0
        if p > 1:
            return 1.0
        return p
    except Exception:
        return default


def weighted_choice(choices, weights):
    # Not used currently; keep for potential extensions
    import random
    return random.choices(choices, weights=weights, k=1)[0]


def safe_eval_template(template: str, row: Dict[str, Any]) -> str:
    # Only allow reading values from row by {col_name}
    # Unknown fields become empty strings
    class SafeDict(dict):
        def __missing__(self, key):
            return ""
    mapping = SafeDict({k: ("" if v is None else str(v)) for k, v in dict(row).items()})
    # Validate that template only contains field names (no format spec with !r or !s)
    for literal_text, field_name, format_spec, conversion in Formatter().parse(template):
        if field_name is None:
            continue
        if conversion is not None:
            raise ValueError("Template conversions are not allowed")
        # Optionally restrict to alphanum and underscore
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", field_name):
            raise ValueError(f"Invalid field in template: {field_name}")
    try:
        return template.format_map(mapping)
    except KeyError:
        return template

