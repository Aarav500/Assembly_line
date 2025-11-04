import os
import re
import math
import subprocess
from typing import List, Tuple, Dict, Any, Optional

BINARY_BYTES = b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0E\x0F"

class SecretScanner:
    def __init__(self):
        self.patterns: List[Tuple[str, re.Pattern]] = [
            ("AWS Access Key ID", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
            ("AWS Secret Access Key", re.compile(r"(?i)aws(.{0,20})?(secret|ssk|secret_access_key)(.{0,20})?[:=]\s*[\'\"]?([A-Za-z0-9/+=]{40})[\'\"]?")),
            ("GitHub Token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
            ("Slack Token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,48}\b")),
            ("Google API Key", re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b")),
            ("Private Key", re.compile(r"-----BEGIN (?:RSA|DSA|EC|OPENSSH) PRIVATE KEY-----")),
            ("Heroku API Key", re.compile(r"\b(?i)heroku[a-z0-9]{32}\b")),
            ("Password Assignment", re.compile(r"(?i)\b(password|passwd|pwd)\s*[:=]\s*[\'\"][^\'\"]{6,}[\'\"]")),
            ("Generic Secret", re.compile(r"(?i)\b(api[_-]?key|token|secret)\s*[:=]\s*[\'\"]?([A-Za-z0-9_\-]{16,})[\'\"]?")),
        ]
        # Entropy candidate regex
        self.base64_candidate = re.compile(r"\b[A-Za-z0-9+/]{20,}={0,2}\b")
        self.hex_candidate = re.compile(r"\b[0-9a-fA-F]{32,}\b")

        # Exclusions to reduce false positives
        self.exclude_dirs = {".git", ".hg", ".svn", ".idea", ".vscode", "node_modules", "venv", ".venv", "__pycache__"}
        self.max_file_size = 1024 * 1024  # 1MB

    def _is_text_file(self, path: str) -> bool:
        try:
            with open(path, 'rb') as f:
                chunk = f.read(1024)
                if not chunk:
                    return True
                if b"\x00" in chunk:
                    return False
                # Heuristic: if many control characters, likely binary
                controls = sum(b < 9 or (13 < b < 32) for b in chunk)
                return controls / max(1, len(chunk)) < 0.3
        except Exception:
            return False

    def _shannon_entropy(self, data: str) -> float:
        if not data:
            return 0.0
        probs = [float(data.count(c)) / len(data) for c in set(data)]
        return -sum(p * math.log(p, 2) for p in probs)

    def _scan_content(self, content: str, rel_path: str) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        lines = content.splitlines()
        for idx, line in enumerate(lines, start=1):
            # Regex rules
            for rule_name, pattern in self.patterns:
                for m in pattern.finditer(line):
                    matched = m.group(0)
                    finding = {
                        "file": rel_path,
                        "line": idx,
                        "col": m.start() + 1,
                        "end_col": m.end(),
                        "match": matched[:200],
                        "rule": rule_name,
                        "entropy": None,
                    }
                    findings.append(finding)
            # Entropy checks per-line
            for m in self.base64_candidate.finditer(line):
                token = m.group(0)
                if len(token) >= 20 and any(c.isalpha() for c in token) and any(c.isdigit() for c in token):
                    ent = self._shannon_entropy(token)
                    if ent >= 4.5:
                        findings.append({
                            "file": rel_path,
                            "line": idx,
                            "col": m.start() + 1,
                            "end_col": m.end(),
                            "match": token[:200],
                            "rule": "High Entropy (base64)",
                            "entropy": round(ent, 3),
                        })
            for m in self.hex_candidate.finditer(line):
                token = m.group(0)
                ent = self._shannon_entropy(token)
                if ent >= 3.0:
                    findings.append({
                        "file": rel_path,
                        "line": idx,
                        "col": m.start() + 1,
                        "end_col": m.end(),
                        "match": token[:200],
                        "rule": "High Entropy (hex)",
                        "entropy": round(ent, 3),
                    })
        return findings

    def _iter_files(self, base_path: str, include_globs=None, exclude_globs=None):
        import fnmatch
        for root, dirs, files in os.walk(base_path):
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]
            for fn in files:
                p = os.path.join(root, fn)
                rel = os.path.relpath(p, base_path)
                if os.path.getsize(p) > self.max_file_size:
                    continue
                if include_globs and not any(fnmatch.fnmatch(rel, g) for g in include_globs):
                    continue
                if exclude_globs and any(fnmatch.fnmatch(rel, g) for g in exclude_globs):
                    continue
                if not self._is_text_file(p):
                    continue
                yield p, rel

    def scan_path(self, path: str, include_globs=None, exclude_globs=None, staged: bool = False) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        findings: List[Dict[str, Any]] = []
        stats = {"files_scanned": 0}
        if staged:
            staged_files = self._get_staged_files(path)
            for rel in staged_files:
                content = self._get_staged_file_content(path, rel)
                if content is None:
                    continue
                stats["files_scanned"] += 1
                findings.extend(self._scan_content(content, rel))
            return findings, stats

        for abs_path, rel_path in self._iter_files(path, include_globs, exclude_globs):
            try:
                with open(abs_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                stats["files_scanned"] += 1
                findings.extend(self._scan_content(content, rel_path))
            except Exception:
                continue
        return findings, stats

    def _get_staged_files(self, repo_path: str) -> List[str]:
        try:
            out = subprocess.check_output(["git", "-C", repo_path, "diff", "--cached", "--name-only"], stderr=subprocess.DEVNULL)
            files = out.decode().splitlines()
            # filter to text-like and under size
            res = []
            for f in files:
                absf = os.path.join(repo_path, f)
                if os.path.exists(absf) and os.path.getsize(absf) > self.max_file_size:
                    continue
                if os.path.exists(absf) and not self._is_text_file(absf):
                    continue
                res.append(f)
            return res
        except Exception:
            return []

    def _get_staged_file_content(self, repo_path: str, rel_path: str) -> Optional[str]:
        try:
            out = subprocess.check_output(["git", "-C", repo_path, "show", f":{rel_path}"], stderr=subprocess.DEVNULL)
            return out.decode(errors='replace')
        except Exception:
            # file might be deleted or binary
            return None

