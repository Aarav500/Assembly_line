import re
from typing import List, Dict, Any

try:
    from radon.complexity import cc_visit
    _HAS_RADON = True
except Exception:
    _HAS_RADON = False


_HEURISTIC_TOKENS = re.compile(r"\\b(if|elif|for|while|case|except|catch|&&|\|\||\?\:|and|or)\\b")


def analyze_python_complexity(code: str, filepath: str) -> Dict[str, Any]:
    results = {
        "path": filepath,
        "functions": 0,
        "avg_cc": 0.0,
        "max_cc": 0.0,
        "most_complex": None,
        "items": [],
        "tool": "radon" if _HAS_RADON else "heuristic",
    }
    if _HAS_RADON:
        try:
            blocks = cc_visit(code)
        except Exception:
            blocks = []
        if not blocks:
            return results
        total_cc = 0.0
        max_item = None
        for b in blocks:
            # b has .complexity and .name and .lineno
            item = {
                "name": getattr(b, "name", "<unknown>"),
                "cc": float(getattr(b, "complexity", 0)),
                "lineno": int(getattr(b, "lineno", 0)),
            }
            results["items"].append(item)
            total_cc += item["cc"]
            if max_item is None or item["cc"] > max_item["cc"]:
                max_item = item
        results["functions"] = len(blocks)
        if results["functions"]:
            results["avg_cc"] = total_cc / results["functions"]
        results["max_cc"] = max_item["cc"] if max_item else 0.0
        results["most_complex"] = max_item
    else:
        # Fallback heuristic: count keywords per function-like scopes roughly by counting 'def' occurrences
        lines = code.splitlines()
        def_count = sum(1 for l in lines if l.strip().startswith("def ") or l.strip().startswith("class "))
        tokens = _HEURISTIC_TOKENS.findall(code)
        complexity_score = len(tokens) + max(0, def_count)
        results["functions"] = max(1, def_count)
        results["avg_cc"] = complexity_score / results["functions"]
        results["max_cc"] = results["avg_cc"]
        results["most_complex"] = {"name": "<heuristic>", "cc": results["avg_cc"], "lineno": 0}
    return results


def heuristic_complexity(code: str, filepath: str, ext: str) -> Dict[str, Any]:
    # For non-Python files, provide a naive heuristic
    tokens = _HEURISTIC_TOKENS.findall(code)
    lines = code.splitlines()
    func_like = 1
    # Approximate function/method counts by language indicators
    if ext in {".js", ".jsx", ".ts", ".tsx"}:
        func_like = sum(1 for l in lines if re.search(r"function |=>|class ", l)) or 1
    elif ext in {".java", ".cs"}:
        func_like = sum(1 for l in lines if re.search(r"class | void | int | String |public |private |protected ", l)) or 1
    elif ext in {".c", ".h", ".cpp", ".cc"}:
        func_like = sum(1 for l in lines if re.search(r"\\w+\\s+\\w+\\s*\\(.*\\)\\s*{", l)) or 1
    elif ext == ".rb":
        func_like = sum(1 for l in lines if re.search(r"def |class ", l)) or 1
    elif ext == ".php":
        func_like = sum(1 for l in lines if re.search(r"function |class ", l)) or 1
    elif ext == ".go":
        func_like = sum(1 for l in lines if re.search(r"func |type ", l)) or 1
    else:
        func_like = 1
    score = len(tokens)
    avg = score / func_like
    return {
        "path": filepath,
        "functions": func_like,
        "avg_cc": float(avg),
        "max_cc": float(avg),
        "most_complex": {"name": "<heuristic>", "cc": float(avg), "lineno": 0},
        "items": [],
        "tool": "heuristic",
    }

