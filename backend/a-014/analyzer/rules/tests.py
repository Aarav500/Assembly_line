import ast
import os
from typing import List, Tuple, Set
from .base import BaseRule, Issue


def is_test_file(path: str) -> bool:
    try:
        fname = os.path.basename(path)
        parts = path.replace("\\", "/").split("/")
        if any(p.lower() == "tests" for p in parts):
            return True
        return fname.startswith("test_") or fname.endswith("_test.py")
    except Exception:
        return False


class TestsRule(BaseRule):
    rule_id = "TESTS"
    name = "Missing or Weak Tests"
    description = "Heuristically detect missing tests or low test coverage"
    category = "tests"
    default_severity = "medium"
    scope = "project"

    def analyze_project(self, files: List[Tuple[str, ast.AST, str]]):
        try:
            # Separate test and non-test files
            test_files = [(p, t, c) for (p, t, c) in files if is_test_file(p)]
            src_files = [(p, t, c) for (p, t, c) in files if not is_test_file(p)]

            issues: List[Issue] = []

            if not test_files:
                # No tests at all
                for p, t, c in src_files:
                    try:
                        issues.append(Issue(
                            rule_id="TESTS_NONE",
                            category="tests",
                            title="No tests found in repository",
                            file=p,
                            line=1,
                            column=0,
                            severity="high",
                            recommendation="Add a tests/ directory with test_*.py files to cover this module.",
                            details="No test files were detected.",
                            tags=["no-tests"],
                        ))
                    except Exception:
                        continue
                return issues

            # Collect referenced names in tests
            referenced_names: Set[str] = set()
            for p, t, c in test_files:
                try:
                    if t is None:
                        continue
                    for n in ast.walk(t):
                        try:
                            if isinstance(n, ast.Name):
                                referenced_names.add(n.id)
                            elif isinstance(n, ast.Attribute):
                                referenced_names.add(n.attr)
                        except Exception:
                            continue
                except Exception:
                    continue
                    
            # For each source module, collect defined functions/classes
            for p, t, c in src_files:
                try:
                    if t is None:
                        # skip syntax error files
                        continue
                    defined: Set[str] = set()
                    for n in t.body:
                        try:
                            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                                defined.add(n.name)
                        except Exception:
                            continue
                            
                    public = {name for name in defined if not name.startswith("_")}
                    if not defined:
                        continue
                    matches = len([n for n in defined if n in referenced_names])
                    ratio = matches / max(1, len(defined))
                    if ratio < 0.3:
                        try:
                            issues.append(Issue(
                                rule_id="TESTS_LOW_COVERAGE_HEURISTIC",
                                category="tests",
                                title=f"Low test coverage by heuristic (match ratio {ratio:.0%})",
                                file=p,
                                line=1,
                                column=0,
                                severity="medium",
                                recommendation="Add unit tests referencing the functions/classes defined in this module.",
                                details=f"Defined names: {', '.join(sorted(defined))}. Only {matches}/{len(defined)} appear in test files.",
                                tags=["low-test-coverage"],
                            ))
                        except Exception:
                            continue
                except Exception:
                    continue

            return issues
        except Exception:
            return []