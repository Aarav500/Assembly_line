from typing import Any, Dict, List, Optional
from .base import BaseAgent

class PlannerAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Planner", role="Decompose task into plan, spec, tests")

    def plan(self, goal: Optional[str], user_tests: Optional[List[Dict[str, Any]]] = None, function_name: Optional[str] = None) -> Dict[str, Any]:
        if user_tests and function_name:
            return {
                "description": goal or f"User-provided tests for {function_name}",
                "function_name": function_name,
                "args": self._infer_args_from_tests(user_tests),
                "tests": user_tests,
                "acceptance_criteria": "All provided tests pass"
            }

        # Heuristic planning from natural language goal
        goal_text = (goal or "").strip()
        plan = self._heuristic_plan(goal_text)
        return plan

    def _infer_args_from_tests(self, tests: List[Dict[str, Any]]) -> List[str]:
        # Simple heuristic: number of args from first test
        if not tests:
            return ["x"]
        first = tests[0].get("input", [])
        if isinstance(first, list):
            return [f"arg{i+1}" for i in range(len(first))]
        return ["x"]

    def _heuristic_plan(self, goal_text: str) -> Dict[str, Any]:
        gt = goal_text.lower()
        # Default structure
        plan: Dict[str, Any] = {
            "description": goal_text,
            "function_name": "identity",
            "args": ["x"],
            "tests": [
                {"input": [5], "expected": 5},
                {"input": ["abc"], "expected": "abc"}
            ],
            "acceptance_criteria": "All tests pass"
        }

        def plan_simple(name: str, args: List[str], tests: List[Dict[str, Any]], desc: str) -> Dict[str, Any]:
            return {
                "description": desc,
                "function_name": name,
                "args": args,
                "tests": tests,
                "acceptance_criteria": "All tests pass"
            }

        if any(k in gt for k in ["add", "sum", "plus"]):
            return plan_simple(
                "add", ["a", "b"],
                [
                    {"input": [1, 2], "expected": 3},
                    {"input": [-1, 5], "expected": 4},
                    {"input": [0, 0], "expected": 0}
                ],
                "Return the sum of two numbers"
            )
        if any(k in gt for k in ["subtract", "minus", "difference"]):
            return plan_simple(
                "subtract", ["a", "b"],
                [
                    {"input": [5, 3], "expected": 2},
                    {"input": [3, 5], "expected": -2}
                ],
                "Return a - b"
            )
        if any(k in gt for k in ["multiply", "product", "times"]):
            return plan_simple(
                "multiply", ["a", "b"],
                [
                    {"input": [2, 3], "expected": 6},
                    {"input": [0, 7], "expected": 0}
                ],
                "Return the product of two numbers"
            )
        if any(k in gt for k in ["divide", "quotient"]):
            return plan_simple(
                "divide", ["a", "b"],
                [
                    {"input": [6, 3], "expected": 2.0, "approx": True},
                    {"input": [7, 2], "expected": 3.5, "approx": True},
                    {"input": [1, 0], "expected": None}
                ],
                "Return a / b, return None for division by zero"
            )
        if "factorial" in gt:
            return plan_simple(
                "factorial", ["n"],
                [
                    {"input": [0], "expected": 1},
                    {"input": [1], "expected": 1},
                    {"input": [5], "expected": 120}
                ],
                "Compute factorial of non-negative integer"
            )
        if any(k in gt for k in ["fibonacci", "fib"]):
            return plan_simple(
                "fibonacci", ["n"],
                [
                    {"input": [0], "expected": 0},
                    {"input": [1], "expected": 1},
                    {"input": [7], "expected": 13}
                ],
                "Compute nth Fibonacci number with F(0)=0, F(1)=1"
            )
        if "prime" in gt:
            return plan_simple(
                "is_prime", ["n"],
                [
                    {"input": [2], "expected": True},
                    {"input": [4], "expected": False},
                    {"input": [17], "expected": True},
                    {"input": [1], "expected": False}
                ],
                "Return True if n is prime"
            )
        if any(k in gt for k in ["reverse", "reversed string", "string reverse"]):
            return plan_simple(
                "reverse_string", ["s"],
                [
                    {"input": ["abc"], "expected": "cba"},
                    {"input": [""], "expected": ""}
                ],
                "Reverse a string"
            )
        if "palindrome" in gt:
            return plan_simple(
                "is_palindrome", ["s"],
                [
                    {"input": ["racecar"], "expected": True},
                    {"input": ["hello"], "expected": False}
                ],
                "Return True if s reads the same backward as forward (case-insensitive)"
            )
        if any(k in gt for k in ["sort", "ascending order"]):
            return plan_simple(
                "sort_numbers", ["lst"],
                [
                    {"input": [[3, 1, 2]], "expected": [1, 2, 3]},
                    {"input": [[5, -1, 0]], "expected": [-1, 0, 5]}
                ],
                "Sort a list of numbers ascending"
            )

        return plan

