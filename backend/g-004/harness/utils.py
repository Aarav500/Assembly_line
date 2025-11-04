import re
from datetime import datetime
from typing import List, Any, Dict


def normalize_text(text: str, ops: List[str] | None) -> str:
    if text is None:
        return ""
    s = str(text)
    if not ops:
        return s
    for op in ops:
        if op == "lower":
            s = s.lower()
        elif op == "upper":
            s = s.upper()
        elif op == "strip":
            s = s.strip()
        elif op == "alnum":
            s = re.sub(r"[^0-9a-zA-Z]+", "", s)
        elif op == "spaces_collapse":
            s = re.sub(r"\s+", " ", s).strip()
    return s


def render_prompt(template: str, variables: Dict[str, Any]) -> str:
    if not template:
        return str(variables.get("input", ""))
    # Very small template engine: replace {{var}} with value, supports only string values
    out = template
    for k, v in variables.items():
        out = out.replace("{{" + str(k) + "}}", str(v))
    return out


def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def apply_postprocess(text: str, ops: List[str] | None) -> str:
    if text is None:
        return ""
    s = str(text)
    if not ops:
        return s
    for op in ops:
        if op == "first_line":
            s = s.splitlines()[0] if s.splitlines() else ""
        elif op == "first_number":
            m = re.search(r"[-+]?[0-9]*\.?[0-9]+", s)
            s = m.group(0) if m else ""
        elif op == "strip":
            s = s.strip()
        elif op == "lower":
            s = s.lower()
        elif op == "upper":
            s = s.upper()
        elif op == "alnum":
            s = re.sub(r"[^0-9a-zA-Z]+", "", s)
        elif op == "spaces_collapse":
            s = re.sub(r"\s+", " ", s).strip()
    return s


def try_float(x: Any):
    try:
        return float(x)
    except Exception:
        return None

