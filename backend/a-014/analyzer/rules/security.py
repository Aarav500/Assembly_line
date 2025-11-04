import ast
from typing import List, Optional
from .base import BaseRule, Issue


class _SecurityVisitor(ast.NodeVisitor):
    def __init__(self):
        self.issues: List[Issue] = []
        self.file: str = ""

    def _add(self, title: str, node: ast.AST, severity: str, recommendation: str, details: Optional[str] = None, tags=None):
        try:
            self.issues.append(Issue(
                rule_id="SEC001",
                category="security",
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
            # Log error but don't fail the entire analysis
            pass

    def visit_Call(self, node: ast.Call):
        try:
            # eval / exec
            if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
                self._add(
                    title=f"Use of {node.func.id}() is dangerous",
                    node=node,
                    severity="high",
                    recommendation="Avoid eval/exec. Use safer alternatives (ast.literal_eval, explicit logic).",
                    tags=["eval-exec"],
                )
            # subprocess.* with shell=True
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess":
                has_shell_true = any((isinstance(kw, ast.keyword) and kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True) for kw in node.keywords)
                if has_shell_true:
                    self._add(
                        title="subprocess with shell=True",
                        node=node,
                        severity="high",
                        recommendation="Avoid shell=True or sanitize inputs strictly; prefer list argv and shell=False.",
                        tags=["subprocess-shell"],
                    )
            # pickle loads
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "pickle" and node.func.attr in {"load", "loads"}:
                self._add(
                    title="Unsafe pickle deserialization",
                    node=node,
                    severity="high",
                    recommendation="Avoid pickle for untrusted data; use safer formats like JSON.",
                    tags=["pickle"],
                )
            # yaml.load without SafeLoader
            if isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "yaml" and node.func.attr == "load":
                    # Check for Loader in keywords referencing SafeLoader
                    loader_kw = next((kw for kw in node.keywords if kw.arg == "Loader"), None)
                    ok = False
                    if loader_kw and isinstance(loader_kw.value, ast.Attribute) and loader_kw.value.attr == "SafeLoader":
                        ok = True
                    if not ok:
                        self._add(
                            title="yaml.load without SafeLoader",
                            node=node,
                            severity="high",
                            recommendation="Use yaml.safe_load() or yaml.load(data, Loader=yaml.SafeLoader).",
                            tags=["yaml"],
                        )
        except Exception as e:
            # Log error but continue visiting other nodes
            pass
        finally:
            self.generic_visit(node)


class SecurityRule(BaseRule):
    rule_id = "SEC"
    name = "Security Issues"
    description = "Detect security vulnerabilities"
    category = "security"
    default_severity = "high"
    scope = "file"

    def analyze_file(self, file_path: str, tree: ast.AST, code: str) -> List[Issue]:
        visitor = _SecurityVisitor()
        visitor.file = file_path
        visitor.visit(tree)
        return visitor.issues
