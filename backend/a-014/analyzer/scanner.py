import os
import fnmatch
import hashlib
from dataclasses import dataclass
from typing import List, Dict, Optional, Any, Iterable, Tuple
import ast
from datetime import datetime

from .utils import iter_python_files, read_file_safely, get_snippet
from .rules.base import Issue, BaseRule
from .rules.bugs import BugsRule
from .rules.security import SecurityRule
from .rules.performance import PerformanceRule
from .rules.tests import TestsRule


@dataclass
class FileData:
    path: str
    code: str
    tree: Optional[ast.AST]


class Scanner:
    def __init__(self, include_categories: Optional[List[str]] = None, exclude_globs: Optional[List[str]] = None, severity_threshold: Optional[str] = None):
        self.include_categories = set([c.lower() for c in include_categories]) if include_categories else None
        self.exclude_globs = exclude_globs or []
        self.severity_threshold = severity_threshold
        self.rules: List[BaseRule] = [
            BugsRule(),
            SecurityRule(),
            PerformanceRule(),
            TestsRule(),
        ]
        if self.include_categories:
            self.rules = [r for r in self.rules if r.category in self.include_categories]

        self._severity_rank = {"low": 1, "medium": 2, "high": 3, "critical": 4}

    def list_rules(self) -> List[BaseRule]:
        return list(self.rules)

    def _should_include_file(self, path: str) -> bool:
        # Apply exclude globs
        for pattern in self.exclude_globs:
            if fnmatch.fnmatch(path, pattern):
                return False
        return True

    def scan(self, root: str) -> Dict[str, Any]:
        files: List[FileData] = []
        errors: List[Dict[str, Any]] = []

        for fpath in iter_python_files(root):
            rel = os.path.relpath(fpath, root)
            # default excludes
            default_excludes = [
                "**/.git/**", "**/.hg/**", "**/.svn/**", "**/__pycache__/**",
                "**/.venv/**", "**/venv/**", "**/env/**", "**/site-packages/**",
                "**/build/**", "**/dist/**", "**/node_modules/**",
            ]
            if any(fnmatch.fnmatch(rel, pat) for pat in default_excludes):
                continue
            if not self._should_include_file(rel):
                continue
            try:
                code = read_file_safely(fpath)
                try:
                    tree = ast.parse(code)
                except SyntaxError as se:
                    tree = None
                    errors.append({
                        "file": rel,
                        "error": f"SyntaxError: {se}",
                    })
                files.append(FileData(rel, code, tree))
            except Exception as e:
                errors.append({"file": rel, "error": str(e)})

        issues: List[Issue] = []
        # File-scoped rules
        for rule in self.rules:
            if rule.scope == "file":
                for fd in files:
                    if fd.tree is None:
                        continue
                    try:
                        new_issues = rule.analyze_file(fd.path, fd.tree, fd.code)
                        issues.extend(new_issues)
                    except Exception as e:
                        errors.append({"file": fd.path, "rule": rule.rule_id, "error": str(e)})
            elif rule.scope == "project":
                try:
                    new_issues = rule.analyze_project([(fd.path, fd.tree, fd.code) for fd in files])
                    issues.extend(new_issues)
                except Exception as e:
                    errors.append({"file": None, "rule": rule.rule_id, "error": str(e)})

        # Apply severity threshold filtering if provided
        if self.severity_threshold:
            thr = self._severity_rank.get(self.severity_threshold.lower(), 1)
            issues = [i for i in issues if self._severity_rank.get(i.severity, 1) >= thr]

        # Transform to dicts and add fingerprint/snippet
        out_items: List[Dict[str, Any]] = []
        for i in issues:
            snippet = None
            try:
                code = next((fd.code for fd in files if fd.path == i.file), None)
                if code:
                    snippet = get_snippet(code, i.line)
            except Exception:
                snippet = None
            d = i.to_dict()
            d["snippet"] = snippet
            # fingerprint for dedup
            fp_src = f"{d.get('rule_id')}|{d.get('file')}|{d.get('line')}|{d.get('title')}"
            d["fingerprint"] = hashlib.sha256(fp_src.encode("utf-8")).hexdigest()[:16]
            out_items.append(d)

        summary = self._summarize(out_items)
        return {
            "backlog": out_items,
            "summary": summary,
            "scanned_files": len(files),
            "errors": errors,
            "generated_at": datetime.utcnow().isoformat() + "Z",
        }

    def _summarize(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        by_category: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        for it in items:
            by_category[it.get("type")] = by_category.get(it.get("type"), 0) + 1
            by_severity[it.get("severity")] = by_severity.get(it.get("severity"), 0) + 1
        return {"by_category": by_category, "by_severity": by_severity, "total": len(items)}

