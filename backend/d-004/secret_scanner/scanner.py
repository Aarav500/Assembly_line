from __future__ import annotations
import re
import math
import subprocess
import fnmatch
import os
from typing import Dict, Any, List, Optional

from .patterns import COMPILED_RULES, SEVERITY_ORDER
from .baseline import fingerprint as make_fingerprint, Baseline

IGNORE_INLINE_TOKEN = "secret-scan: ignore"

BASE64_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")
HEX_CHARS = set("0123456789abcdefABCDEF")


def is_path_ignored(path: str, config: Dict[str, Any]) -> bool:
    ignore_patterns = config.get("ignore_paths", []) or []
    for pat in ignore_patterns:
        if fnmatch.fnmatch(path, pat):
            return True
    return False


def matches_allowlist(s: str, config: Dict[str, Any]) -> bool:
    allow_patterns = config.get("allow_patterns", []) or []
    for pat in allow_patterns:
        try:
            if re.search(pat, s):
                return True
        except re.error:
            # Skip invalid allow regex
            continue
    return False


def entropy(s: str) -> float:
    if not s:
        return 0.0
    # Shannon entropy over character distribution
    prob = [float(s.count(c)) / len(s) for c in set(s)]
    return -sum(p * math.log(p, 2) for p in prob)


def high_entropy_candidates(text: str) -> List[re.Match]:
    # Identify candidate tokens with base64-like or hex-like characters, length >= 20
    # We'll use two patterns and merge matches.
    candidates: List[re.Match] = []
    for pat in [r"[A-Za-z0-9+/=]{20,}", r"[A-Fa-f0-9]{32,}"]:
        for m in re.finditer(pat, text):
            token = m.group(0)
            # Basic filters: avoid long runs of the same char
            if len(set(token)) < 6:
                continue
            candidates.append(m)
    return candidates


def compute_line_col(text: str, index: int) -> tuple[int, int]:
    # Compute 1-based line and column from index in text
    line = text.count("\n", 0, index) + 1
    last_nl = text.rfind("\n", 0, index)
    col = index - (last_nl + 1)
    return line, col + 1


def is_binary_string(data: str) -> bool:
    # Heuristic: if it contains a NULL char, treat as binary
    return "\x00" in data


def scan_content(content: str, path: str, config: Dict[str, Any], baseline: Optional[Baseline] = None) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []

    if is_path_ignored(path, config):
        return findings

    if is_binary_string(content):
        return findings

    excluded_rules = set(config.get("excluded_rules", []) or [])

    # Inline ignore support
    lines = content.splitlines()

    # Pre-scan allow patterns at file level
    if matches_allowlist(path, config):
        return findings

    # Rule-based scanning
    for rule in COMPILED_RULES:
        if rule["id"] in excluded_rules:
            continue
        pattern = rule["pattern"]
        if rule.get("multiline"):
            for m in pattern.finditer(content):
                matched = m.group(0)
                start = m.start()
                line, col = compute_line_col(content, start)
                # Inline ignore check
                if line - 1 < len(lines) and IGNORE_INLINE_TOKEN in lines[line - 1]:
                    continue
                if matches_allowlist(matched, config):
                    continue
                fp = make_fingerprint(rule["id"], path, matched)
                if baseline and baseline.contains(fp):
                    continue
                findings.append({
                    "file": path,
                    "line": line,
                    "column": col,
                    "match": matched[:2000],
                    "rule_id": rule["id"],
                    "rule_name": rule["name"],
                    "message": rule["description"],
                    "severity": rule["severity"],
                    "fingerprint": fp,
                    "tags": rule.get("tags", []),
                })
        else:
            for m in pattern.finditer(content):
                matched = m.group(0)
                start = m.start()
                line, col = compute_line_col(content, start)
                if line - 1 < len(lines) and IGNORE_INLINE_TOKEN in lines[line - 1]:
                    continue
                if matches_allowlist(matched, config):
                    continue
                fp = make_fingerprint(rule["id"], path, matched)
                if baseline and baseline.contains(fp):
                    continue
                findings.append({
                    "file": path,
                    "line": line,
                    "column": col,
                    "match": matched[:2000],
                    "rule_id": rule["id"],
                    "rule_name": rule["name"],
                    "message": rule["description"],
                    "severity": rule["severity"],
                    "fingerprint": fp,
                    "tags": rule.get("tags", []),
                })

    # High-entropy scanning
    if config.get("enable_high_entropy", True):
        threshold = float(config.get("entropy_threshold", 4.5))
        for m in high_entropy_candidates(content):
            token = m.group(0)
            # Filter tokens that look like common non-secret patterns
            if token.lower().startswith("http"):
                continue
            e = entropy(token)
            if e >= threshold:
                start = m.start()
                line, col = compute_line_col(content, start)
                if line - 1 < len(lines) and IGNORE_INLINE_TOKEN in lines[line - 1]:
                    continue
                if matches_allowlist(token, config):
                    continue
                rule_id = "HIGH_ENTROPY_STRING"
                rule_name = "High-entropy string"
                fp = make_fingerprint(rule_id, path, token)
                if baseline and baseline.contains(fp):
                    continue
                findings.append({
                    "file": path,
                    "line": line,
                    "column": col,
                    "match": token[:2000],
                    "rule_id": rule_id,
                    "rule_name": rule_name,
                    "message": f"High-entropy string (H={e:.2f}) exceeds threshold {threshold}",
                    "severity": "medium",
                    "fingerprint": fp,
                    "tags": ["entropy"],
                })

    return findings


def list_staged_files() -> List[str]:
    try:
        res = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMRTUXB"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        files = [line.strip() for line in res.stdout.splitlines() if line.strip()]
        return files
    except Exception:
        return []


def read_staged_file(path: str) -> Optional[str]:
    try:
        res = subprocess.run(
            ["git", "show", f":{path}"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return res.stdout
    except Exception:
        return None


def scan_file(path: str, config: Dict[str, Any], baseline: Optional[Baseline]) -> List[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return []
    return scan_content(content, path, config, baseline)


def severity_to_level(sev: str) -> int:
    return SEVERITY_ORDER.get((sev or "").lower(), 1)


__all__ = [
    "scan_content",
    "scan_file",
    "list_staged_files",
    "read_staged_file",
    "severity_to_level",
]

