import ast
from typing import List, Optional
from .base import BaseRule, Issue


class _PerfVisitor(ast.NodeVisitor):
    def __init__(self):
        self.issues: List[Issue] = []
        self.file: str = ""
        self._string_vars_init_lines = set()

    def _add(self, title: str, node: ast.AST, severity: str, recommendation: str, details: Optional[str] = None, tags=None):
        try:
            self.issues.append(Issue(
                rule_id="PERF001",
                category="performance",
                title=title,
                file=self.file,
                line=getattr(node, 'lineno', None),
                column=getattr(node, 'col_offset', None),
                severity=severity,
                recommendation=recommendation,
                details=details,
                tags=tags or [],
            ))
        except Exception as e:
            # Log error but don't stop analysis
            pass

    def visit_Assign(self, node: ast.Assign):
        try:
            # Track simple x = "" initializations
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        self._string_vars_init_lines.add((t.id, node.lineno))
            self.generic_visit(node)
        except Exception as e:
            # Continue visiting other nodes
            pass

    def visit_For(self, node: ast.For):
        try:
            # Nested loops heuristic
            for child in node.body:
                if isinstance(child, ast.For):
                    self._add(
                        title="Nested loops may be O(N^2)",
                        node=child,
                        severity="medium",
                        recommendation="Consider algorithmic improvements, batching, or using vectorized operations.",
                        tags=["nested-loops"],
                    )
            # String concatenation in loop: x += "..." or x = x + "..."
            for child in ast.walk(node):
                if isinstance(child, ast.AugAssign) and isinstance(child.op, ast.Add) and isinstance(child.target, ast.Name):
                    if isinstance(child.value, (ast.Constant, ast.Name, ast.Call, ast.JoinedStr)):
                        self._add(
                            title="String concatenation in loop",
                            node=child,
                            severity="low",
                            recommendation="Use list accumulation and ''.join(...) outside the loop for better performance.",
                            tags=["str-plus-loop"],
                        )
                if isinstance(child, ast.Assign) and len(child.targets) == 1 and isinstance(child.targets[0], ast.Name):
                    target = child.targets[0]
                    if isinstance(child.value, ast.BinOp) and isinstance(child.value.op, ast.Add):
                        # x = x + something
                        left = child.value.left
                        if isinstance(left, ast.Name) and left.id == target.id:
                            self._add(
                                title="Repeated concatenation in loop",
                                node=child,
                                severity="low",
                                recommendation="Accumulate in a list and join once after the loop.",
                                tags=["str-plus-loop"],
                            )
            self.generic_visit(node)
        except Exception as e:
            # Continue visiting other nodes
            pass


class PerformanceRule(BaseRule):
    rule_id = "PERF"
    name = "Performance Issues"
    description = "Detect performance anti-patterns"
    category = "performance"
    default_severity = "low"
    scope = "file"

    def analyze_file(self, file_path: str, tree: ast.AST, code: str) -> List[Issue]:
        visitor = _PerfVisitor()
        visitor.file = file_path
        visitor.visit(tree)
        return visitor.issues
