import re
from typing import Dict, List


def _from_error_message(msg: str) -> List[str]:
    s = []
    if not msg:
        return s

    # ImportError / ModuleNotFoundError
    m = re.search(r"(?:No module named|ModuleNotFoundError: No module named) ['\"]([^'\"]+)['\"]", msg)
    if m:
        pkg = m.group(1)
        s.append(f"pip install {pkg}")
        s.append(f"add 'import {pkg}' at the top of the file")

    # NameError
    m = re.search(r"NameError: name ['\"]([^'\"]+)['\"] is not defined", msg)
    if m:
        name = m.group(1)
        s.append(f"define '{name}' before use or import it")

    # AttributeError
    m = re.search(r"AttributeError: '([^']+)' object has no attribute ['\"]([^'\"]+)['\"]", msg)
    if m:
        attr = m.group(2)
        s.append(f"use correct attribute name instead of '{attr}'")

    # SyntaxError
    if "SyntaxError" in msg:
        s.append("fix Python syntax at the reported location")

    # IndentationError
    if "IndentationError" in msg:
        s.append("fix indentation to 4 spaces per level")

    # FileNotFoundError
    m = re.search(r"FileNotFoundError: \[Errno 2\] No such file or directory: ['\"]([^'\"]+)['\"]", msg)
    if m:
        path = m.group(1)
        s.append(f"ensure '{path}' exists or update the file path")

    # TypeError common case: missing positional argument
    m = re.search(r"TypeError: (\w+)\(\) missing (?:\d+ )?required positional argument", msg)
    if m:
        s.append("pass all required positional arguments to the function")

    return s


def _from_code_snippet(code: str) -> List[str]:
    s = []
    if not code:
        return s

    # Python 2 style print
    if re.search(r"(^|\n)\s*print\s+[^\(].*", code):
        s.append("wrap print arguments in parentheses: use print(...) ")

    # Compare to None with ==
    if re.search(r"==\s*None|None\s*==", code):
        s.append("compare to None using 'is None' or 'is not None'")

    # Unused import common flake8
    if re.search(r"^\s*import\s+\w+\s*(\n|$)", code, re.M) and not re.search(r"\b\w+\.", code):
        s.append("remove unused imports")

    # Trailing whitespace
    if re.search(r"[ \t]+\n", code):
        s.append("remove trailing whitespace")

    # Missing newline at EOF
    if not code.endswith("\n"):
        s.append("add a newline at the end of file")

    return s


def _from_diff(diff: str) -> List[str]:
    s = []
    if not diff:
        return s

    # Detect debug prints
    if re.search(r"^\+.*print\(", diff, re.M):
        s.append("remove debug print statements before commit")

    # Detect commented-out code additions
    if re.search(r"^\+\s*#.*", diff, re.M):
        s.append("remove commented-out code")

    return s


def suggest_one_line_fixes(payload: Dict) -> List[str]:
    suggestions: List[str] = []

    err = payload.get("error") or payload.get("error_message") or ""
    code = payload.get("code") or payload.get("code_snippet") or ""
    diff = payload.get("diff") or payload.get("patch") or ""
    text = payload.get("text") or payload.get("message") or ""

    suggestions.extend(_from_error_message(err))
    suggestions.extend(_from_code_snippet(code))
    suggestions.extend(_from_diff(diff))

    # Generic fallbacks if nothing was found, try from text
    if not suggestions and text:
        suggestions.extend(_from_error_message(text))
        suggestions.extend(_from_code_snippet(text))

    # Always provide a minimal generic suggestion if still empty
    if not suggestions:
        suggestions.append("fix the immediate cause indicated by the last error line")

    # De-duplicate while preserving order
    seen = set()
    deduped: List[str] = []
    for item in suggestions:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped[:10]

