import ast
from typing import List, Optional
from .base import BaseRule, Issue
import builtins


_BUILTIN_NAMES = set(dir(builtins))


class _BugsVisitor(ast.NodeVisitor):
    def __init__(self):
        self.issues: List[Issue] = []
        self.file: str = ""

    def _add(self, title: str, node: ast.AST, severity: str, recommendation: str, details: Optional[str] = None, tags=None):
        self.issues.append(Issue(
            rule_id="BUGS001",
            category="bugs",
            title=title,
            file=self.file,
            line=getattr(node, 'lineno', None),
            column=getattr(node, 'col_offset', None),
            severity=severity,
            recommendation=recommendation,
            details=details,
            tags=tags or [],
        ))

    def visit_FunctionDef(self, node: ast.FunctionDef):
        try:
            # Mutable default args
            for d in (node.args.defaults or []) + (node.args.kw_defaults or []):
                if isinstance(d, (ast.List, ast.Dict, ast.Set)):
                    self._add(
                        title=f"Mutable default argument in function '{node.name}'",
                        node=node,
                        severity="high",
                        recommendation="Use None as default and assign a new list/dict/set inside the function.",
                        details="Mutable defaults are shared between calls and can cause surprising bugs.",
                        tags=["mutable-default"],
                    )
            # Return type inconsistency
            returns_values = []
            for child in ast.walk(node):
                if isinstance(child, ast.Return):
                    returns_values.append(child.value is not None)
            if returns_values and any(returns_values) and not all(returns_values):
                self._add(
                    title=f"Inconsistent return values in function '{node.name}'",
                    node=node,
                    severity="medium",
                    recommendation="Ensure all code paths return a value or all return None for consistency.",
                    details="Function has returns with and without values.",
                    tags=["inconsistent-return"],
                )
            # Unreachable code after return/raise/break/continue (basic heuristic)
            terminators = (ast.Return, ast.Raise, ast.Break, ast.Continue)
            body = list(node.body)
            found_term = False
            for stmt in body:
                if found_term:
                    self._add(
                        title=f"Unreachable code in function '{node.name}'",
                        node=stmt,
                        severity="low",
                        recommendation="Remove or refactor unreachable statements.",
                        details="Statement appears after a guaranteed control-flow terminator.",
                        tags=["unreachable"],
                    )
                    break
                if isinstance(stmt, terminators):
                    found_term = True
            self.generic_visit(node)
        except Exception as e:
            # Log error but continue processing other nodes
            pass

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        try:
            self.generic_visit(node)
        except Exception as e:
            pass


class BugsRule(BaseRule):
    rule_id = "BUGS"
    name = "Bug Detection"
    description = "Detect common bug patterns"
    category = "bugs"
    default_severity = "medium"
    scope = "file"

    def analyze_file(self, file_path: str, tree: ast.AST, code: str) -> List[Issue]:
        visitor = _BugsVisitor()
        visitor.file = file_path
        visitor.visit(tree)
        return visitor.issues
