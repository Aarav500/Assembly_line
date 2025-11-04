from __future__ import annotations
import re
from typing import Tuple, List, Dict, Any
from json import JSONDecodeError
from jsonpath_ng import parse as jsonpath_parse


def evaluate_checks(response, elapsed_ms: float, checks: List[Any]) -> Tuple[bool, List[Dict[str, Any]], str | None]:
    details = []
    all_ok = True
    first_error = None
    body_text = None
    json_doc = None

    # prepare body
    try:
        body_text = response.text
    except Exception:
        body_text = ""

    for chk in checks or []:
        ok = True
        info = {"type": chk.type, "op": chk.op, "expected": chk.expected, "path": chk.path}
        try:
            if chk.type == "status_code":
                ok = _apply_op(response.status_code, chk.op or "eq", chk.expected)
            elif chk.type == "response_time_ms":
                ok = _apply_op(elapsed_ms, chk.op or "lt", float(chk.expected))
            elif chk.type == "contains":
                ok = (chk.expected in (body_text or ""))
            elif chk.type == "regex":
                pattern = str(chk.expected)
                ok = re.search(pattern, body_text or "") is not None
            elif chk.type == "jsonpath":
                if json_doc is None:
                    try:
                        json_doc = response.json()
                    except JSONDecodeError:
                        json_doc = None
                if json_doc is None:
                    ok = False
                else:
                    expr = jsonpath_parse(chk.path or "$")
                    matches = [m.value for m in expr.find(json_doc)]
                    if chk.op in (None, "exists"):
                        ok = len(matches) > 0
                    elif chk.op == "eq":
                        ok = any(m == chk.expected for m in matches)
                    elif chk.op == "ne":
                        ok = any(m != chk.expected for m in matches)
                    elif chk.op == "in":
                        ok = chk.expected in matches
                    else:
                        ok = False
            else:
                ok = False
        except Exception as e:
            ok = False
            info["error"] = str(e)

        info["success"] = ok
        if not ok:
            all_ok = False
            if not first_error:
                first_error = f"check failed: {info}"
        details.append(info)

    return all_ok, details, first_error


def _apply_op(actual, op: str, expected) -> bool:
    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    if op == "lt":
        return actual < expected
    if op == "lte":
        return actual <= expected
    if op == "gt":
        return actual > expected
    if op == "gte":
        return actual >= expected
    if op == "in":
        return actual in expected
    return False

