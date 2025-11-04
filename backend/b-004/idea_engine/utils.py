import re
import datetime as _dt
from typing import Dict, Any
from jinja2 import Environment, StrictUndefined

class ValidationError(Exception):
    def __init__(self, message: str, details=None):
        super().__init__(message)
        self.details = details or {}

def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9\-\s]", "", value)
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"-+", "-", value)
    return value

def _titlecase(value: str) -> str:
    return re.sub(r"\b(\w)", lambda m: m.group(1).upper(), value)

def _money(value, symbol: str = "$", precision: int = 2) -> str:
    try:
        num = float(value)
    except Exception:
        return str(value)
    return f"{symbol}{num:,.{precision}f}"


def build_env() -> Environment:
    env = Environment(undefined=StrictUndefined, autoescape=False, trim_blocks=True, lstrip_blocks=True)
    env.filters["slugify"] = _slugify
    env.filters["titlecase"] = _titlecase
    env.filters["money"] = _money
    return env


def base_context(extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
    now = _dt.datetime.utcnow()
    ctx = {
        "now": now,
        "today": now.date().isoformat(),
        "year": now.year,
    }
    if extra:
        ctx.update(extra)
    return ctx


def validate_inputs(fields_spec, inputs: Dict[str, Any]):
    errors = {}
    clean = {}
    for f in fields_spec:
        name = f.name
        val = inputs.get(name, f.default)
        if f.required and (val is None or (isinstance(val, str) and val.strip() == "")):
            errors[name] = "This field is required"
            continue
        if val is None:
            val = ""
        if f.type == "number" and val != "":
            try:
                val = float(val)
            except Exception:
                errors[name] = "Must be a number"
                continue
        if f.type == "select" and f.options and val not in f.options:
            errors[name] = f"Must be one of: {', '.join(map(str, f.options))}"
            continue
        clean[name] = val
    if errors:
        raise ValidationError("Invalid inputs", details=errors)
    return clean

