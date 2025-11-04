import os
import re
import json
import math
from typing import Dict, List, Tuple

# Common directory patterns to skip
SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "vendor", "venv", ".venv",
    "dist", "build", "__pycache__", ".idea", ".vscode", ".tox", "target",
}

# File extensions to skip as binary-heavy
SKIP_FILE_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".ico",
    ".pdf", ".zip", ".gz", ".tar", ".7z", ".rar",
    ".exe", ".dll", ".so", ".dylib",
    ".woff", ".woff2", ".ttf", ".otf",
    ".mp3", ".mp4", ".mov", ".avi", ".mkv",
}

# Regex patterns for common secrets
PATTERNS = [
    {
        "id": "aws_access_key_id",
        "name": "AWS Access Key ID",
        "regex": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "severity": "high",
    },
    {
        "id": "aws_secret_access_key",
        "name": "AWS Secret Access Key",
        "regex": re.compile(r"(?i)(?:aws_)?secret(?:_access)?_key\s*[:=]\s*([A-Za-z0-9/+=]{40})"),
        "severity": "critical",
        "group": 1,
    },
    {
        "id": "private_key_block",
        "name": "Private Key",
        "regex": re.compile(r"-----BEGIN (?:RSA|DSA|EC|PGP|OPENSSH) PRIVATE KEY-----"),
        "severity": "critical",
    },
    {
        "id": "github_token",
        "name": "GitHub Token",
        "regex": re.compile(r"\bghp_[A-Za-z0-9]{36}\b|\bgho_[A-Za-z0-9]{36}\b|\bghu_[A-Za-z0-9]{36}\b|\bghs_[A-Za-z0-9]{36}\b"),
        "severity": "high",
    },
    {
        "id": "slack_token",
        "name": "Slack Token",
        "regex": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
        "severity": "high",
    },
    {
        "id": "google_api_key",
        "name": "Google API Key",
        "regex": re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b"),
        "severity": "medium",
    },
    {
        "id": "stripe_secret_key",
        "name": "Stripe Secret Key",
        "regex": re.compile(r"\bsk_(?:live|test)_[0-9a-zA-Z]{24,}\b"),
        "severity": "high",
    },
    {
        "id": "twilio_api_key",
        "name": "Twilio API Key",
        "regex": re.compile(r"\bSK[0-9a-fA-F]{32}\b"),
        "severity": "medium",
    },
    {
        "id": "bearer_token",
        "name": "Bearer Token",
        "regex": re.compile(r"(?i)\bbearer\s+([A-Za-z0-9\-\._~\+/]+=*)"),
        "severity": "medium",
        "group": 1,
    },
]

# High-entropy candidate matchers
HEX_CANDIDATE = re.compile(r"\b[0-9a-fA-F]{40,}\b")
B64_CANDIDATE = re.compile(r"\b(?:[A-Za-z0-9+/]{40,}={0,2})\b")
JWT_CANDIDATE = re.compile(r"\beyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\b")

ALLOWLIST_HINTS = [
    re.compile(r"(?i)sample|example|dummy|fake|test_key|do_not_detect|not_secret"),
]

ENGINE_META = {
    "name": "builtin-secret-scanner",
    "version": "1.0.0",
}


def is_probably_binary(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            chunk = f.read(8192)
            if b"\x00" in chunk:
                return True
            # Heuristic: if >30% bytes are non-text control, treat as binary
            text_chars = bytearray({7, 8, 9, 10, 12, 13, 27})
            text_chars.extend(range(0x20, 0x100))
            nontext = sum(b not in text_chars for b in chunk)
            if len(chunk) > 0 and (nontext / len(chunk)) > 0.30:
                return True
    except Exception:
        return True
    return False


def shannon_entropy(data: str) -> float:
    if not data:
        return 0.0
    entropy = 0.0
    length = len(data)
    for x in set(data):
        p_x = float(data.count(x)) / length
        entropy -= p_x * math.log(p_x, 2)
    return entropy


def mask_value(val: str) -> str:
    if val is None:
        return ""
    if len(val) <= 8:
        return "*" * max(0, len(val) - 2) + val[-2:]
    return val[:4] + "*" * max(0, len(val) - 8) + val[-4:]


def should_skip_file(path: str, max_file_size: int) -> Tuple[bool, str]:
    _, ext = os.path.splitext(path.lower())
    if ext in SKIP_FILE_EXTS:
        return True, "skipped_extension"
    try:
        size = os.path.getsize(path)
        if size > max_file_size:
            return True, "file_too_large"
    except Exception:
        return True, "stat_failed"
    if is_probably_binary(path):
        return True, "binary"
    return False, ""


def line_has_allowlist(line: str) -> bool:
    for pat in ALLOWLIST_HINTS:
        if pat.search(line):
            return True
    return False


def relative_path(root: str, full: str) -> str:
    try:
        return os.path.relpath(full, root)
    except Exception:
        return full


def scan_file(path: str, root_path: str, findings: List[dict]):
    rel = relative_path(root_path, path)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for idx, line in enumerate(f, start=1):
                # Skip clear allowlist hints
                if line_has_allowlist(line):
                    continue

                # Regex patterns
                for p in PATTERNS:
                    regex = p["regex"]
                    for m in regex.finditer(line):
                        value = None
                        if "group" in p:
                            try:
                                value = m.group(p["group"]) or m.group(0)
                            except Exception:
                                value = m.group(0)
                        else:
                            value = m.group(0)
                        findings.append({
                            "type": p["id"],
                            "title": p["name"],
                            "severity": p.get("severity", "medium"),
                            "file": rel,
                            "line": idx,
                            "match": mask_value(value),
                            "pattern": p["id"],
                            "snippet": line.strip()[:500],
                        })

                # High-entropy candidates
                for m in HEX_CANDIDATE.finditer(line):
                    token = m.group(0)
                    ent = shannon_entropy(token)
                    if ent >= 3.3 and len(token) >= 40:
                        findings.append({
                            "type": "high_entropy_hex",
                            "title": "High-entropy hex string",
                            "severity": "medium",
                            "file": rel,
                            "line": idx,
                            "match": mask_value(token),
                            "entropy": round(ent, 2),
                            "snippet": line.strip()[:500],
                        })

                for m in B64_CANDIDATE.finditer(line):
                    token = m.group(0)
                    ent = shannon_entropy(token)
                    if ent >= 4.0 and len(token) >= 40:
                        findings.append({
                            "type": "high_entropy_base64",
                            "title": "High-entropy base64-like string",
                            "severity": "medium",
                            "file": rel,
                            "line": idx,
                            "match": mask_value(token),
                            "entropy": round(ent, 2),
                            "snippet": line.strip()[:500],
                        })

                for m in JWT_CANDIDATE.finditer(line):
                    token = m.group(0)
                    # JWT-like tokens are likely sensitive
                    findings.append({
                        "type": "jwt_token",
                        "title": "JWT-like token",
                        "severity": "medium",
                        "file": rel,
                        "line": idx,
                        "match": mask_value(token),
                        "snippet": line.strip()[:500],
                    })
    except Exception as e:
        # Ignore unreadable files
        return


def scan_directory(root_path: str, max_file_size: int, max_files: int) -> dict:
    """
    Scan a directory for secrets.
    Returns a dict with summary, findings, warnings, truncated flag, and engine info.
    """
    findings = []
    warnings = []
    files_scanned = 0
    files_skipped = 0
    truncated = False

    for dirpath, dirnames, filenames in os.walk(root_path):
        # Skip certain directories
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        for filename in filenames:
            if files_scanned >= max_files:
                truncated = True
                warnings.append(f"Reached max file limit ({max_files}), scan truncated")
                break

            full_path = os.path.join(dirpath, filename)
            skip, reason = should_skip_file(full_path, max_file_size)
            if skip:
                files_skipped += 1
                continue

            scan_file(full_path, root_path, findings)
            files_scanned += 1

        if truncated:
            break

    # Build summary by severity
    summary = {
        "total_findings": len(findings),
        "files_scanned": files_scanned,
        "files_skipped": files_skipped,
        "by_severity": {},
    }

    for finding in findings:
        sev = finding.get("severity", "unknown")
        summary["by_severity"][sev] = summary["by_severity"].get(sev, 0) + 1

    return {
        "summary": summary,
        "findings": findings,
        "warnings": warnings,
        "truncated": truncated,
        "engine": ENGINE_META,
    }
