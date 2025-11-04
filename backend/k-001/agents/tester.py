import traceback
import time
from typing import Any, Dict, List
from .base import BaseAgent

class TesterAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Tester", role="Run tests and report results")

    def test(self, artifact: Dict[str, Any], tests: List[Dict[str, Any]], float_tol: float = 1e-6) -> Dict[str, Any]:
        code = artifact.get("code", "")
        func_name = artifact.get("function_name")

        safe_builtins = {
            "range": range,
            "len": len,
            "enumerate": enumerate,
            "sum": sum,
            "min": min,
            "max": max,
            "abs": abs,
            "all": all,
            "any": any,
            "sorted": sorted,
            "list": list,
            "dict": dict,
            "set": set,
            "float": float,
            "int": int,
            "str": str,
            "bool": bool,
        }
        env = {"__builtins__": safe_builtins}
        try:
            exec(code, env, env)
        except Exception as e:
            return {
                "passed": False,
                "passed_count": 0,
                "failed_count": len(tests),
                "results": [
                    {"input": None, "expected": None, "passed": False, "error": f"Code exec error: {e}", "traceback": traceback.format_exc()}
                ]
            }
        func = env.get(func_name)
        if not callable(func):
            return {
                "passed": False,
                "passed_count": 0,
                "failed_count": len(tests),
                "results": [
                    {"input": None, "expected": None, "passed": False, "error": f"Function '{func_name}' not found"}
                ]
            }

        results = []
        passed_count = 0
        for t in tests:
            args = t.get("input", [])
            expected = t.get("expected")
            approx = bool(t.get("approx", False))
            start = time.time()
            try:
                got = func(*args) if isinstance(args, list) else func(args)
                ok = self._compare(got, expected, approx, float_tol)
                if ok:
                    passed_count += 1
                results.append({
                    "input": args,
                    "expected": expected,
                    "got": got,
                    "passed": ok,
                    "duration_ms": round((time.time() - start) * 1000, 3)
                })
            except Exception as e:
                results.append({
                    "input": args,
                    "expected": expected,
                    "passed": False,
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "duration_ms": round((time.time() - start) * 1000, 3)
                })
        failed_count = len(tests) - passed_count
        return {
            "passed": failed_count == 0,
            "passed_count": passed_count,
            "failed_count": failed_count,
            "results": results
        }

    def _compare(self, got: Any, expected: Any, approx: bool, tol: float) -> bool:
        # Exact match
        if type(expected) == float or type(got) == float:
            if approx:
                try:
                    return abs(float(got) - float(expected)) <= tol
                except Exception:
                    return False
        return got == expected

