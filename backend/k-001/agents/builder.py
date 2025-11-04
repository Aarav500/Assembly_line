import os
from typing import Any, Dict, List
from .base import BaseAgent

class BuilderAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Builder", role="Implement code from plan")

    def build(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        fname = plan.get("function_name", "identity")
        args: List[str] = plan.get("args", ["x"]) or ["x"]
        desc = plan.get("description", f"Function {fname}")

        code = self._generate_code(fname, args, desc)

        os.makedirs("artifacts", exist_ok=True)
        file_path = os.path.join("artifacts", f"{fname}.py")
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)
        except Exception:
            file_path = None

        return {
            "function_name": fname,
            "code": code,
            "file_path": file_path
        }

    def _generate_code(self, fname: str, args: List[str], desc: str) -> str:
        sig = ", ".join(args)
        # Library of simple implementations
        impl = ""
        if fname == "add":
            impl = f"return a + b"
        elif fname == "subtract":
            impl = f"return a - b"
        elif fname == "multiply":
            impl = f"return a * b"
        elif fname == "divide":
            impl = (
                "if b == 0:\n"
                "        return None\n"
                "    return a / b\n"
            )
        elif fname == "factorial":
            impl = (
                "if n < 0:\n"
                "        raise ValueError('n must be non-negative')\n"
                "    result = 1\n"
                "    for i in range(2, n+1):\n"
                "        result *= i\n"
                "    return result\n"
            )
        elif fname == "fibonacci":
            impl = (
                "if n < 0:\n"
                "        raise ValueError('n must be non-negative')\n"
                "    a, b = 0, 1\n"
                "    for _ in range(n):\n"
                "        a, b = b, a + b\n"
                "    return a\n"
            )
        elif fname == "is_prime":
            impl = (
                "if n <= 1:\n"
                "        return False\n"
                "    if n <= 3:\n"
                "        return True\n"
                "    if n % 2 == 0 or n % 3 == 0:\n"
                "        return False\n"
                "    i = 5\n"
                "    while i * i <= n:\n"
                "        if n % i == 0 or n % (i + 2) == 0:\n"
                "            return False\n"
                "        i += 6\n"
                "    return True\n"
            )
        elif fname == "reverse_string":
            impl = "return s[::-1]"
        elif fname == "is_palindrome":
            impl = (
                "t = ''.join(ch.lower() for ch in s if ch.isalnum())\n"
                "    return t == t[::-1]\n"
            )
        elif fname == "sort_numbers":
            impl = "return sorted(lst)"
        else:
            # identity fallback
            impl = "return x"

        code = (
            "\n".join([
                f"def {fname}({sig}):",
                f"    \"\"\"{desc}\"\"\"",
                f"    {impl}",
                "",
                "# You can add more helper functions below if needed.",
                ""
            ])
        )
        return code

