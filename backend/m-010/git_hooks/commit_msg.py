#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
from typing import Dict, List

# Make src importable when running from .git/hooks or project root
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(THIS_DIR, os.pardir))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

EXPLAIN_TRAILER_LABEL = os.environ.get("EXPLAIN_TRAILER_LABEL", "Explain-Change")
AI_TRAILER_LABEL = os.environ.get("AI_TRAILER_LABEL", "AI-Generated")
SERVICE_URL = os.environ.get("EXPLAIN_SERVICE_URL")
TIMEOUT = float(os.environ.get("EXPLAIN_SERVICE_TIMEOUT", "5"))


def _run(cmd: List[str]) -> str:
    return subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode("utf-8", errors="replace")


def _get_name_status() -> List[List[str]]:
    # Format: <status>\t<path> or Rxxx\t<old>\t<new>
    out = _run(["git", "diff", "--cached", "--name-status"])
    files = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0].strip()
        if status.startswith('R') or status.startswith('C'):
            # rename/copy with score
            if len(parts) >= 3:
                old_p, new_p = parts[1], parts[2]
                files.append([status[0], new_p, old_p])
            else:
                files.append([status[0], parts[-1], None])
        else:
            files.append([status[0], parts[1], None])
    return files


def _get_numstat() -> Dict[str, Dict[str, int]]:
    # Format: <additions> <deletions> <path>
    out = _run(["git", "diff", "--cached", "--numstat"])
    stats: Dict[str, Dict[str, int]] = {}
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        add_s, del_s, path = parts[0], parts[1], parts[2]
        try:
            a = int(add_s) if add_s.isdigit() else 0
            d = int(del_s) if del_s.isdigit() else 0
        except ValueError:
            a, d = 0, 0
        stats[path] = {"additions": a, "deletions": d}
    return stats


def _read_commit_message(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _write_commit_message(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _has_truthy_trailer(content: str, label: str) -> bool:
    # Match trailers like: Label: true
    pattern = re.compile(rf"(?mi)^\s*{re.escape(label)}\s*:\s*(.+?)\s*$")
    m = pattern.search(content)
    if not m:
        return False
    val = m.group(1).strip().lower()
    return val in {"1", "true", "yes", "y"}


def _has_trailer(content: str, label: str) -> bool:
    pattern = re.compile(rf"(?mi)^\s*{re.escape(label)}\s*:\s*(.+?)\s*$")
    return bool(pattern.search(content))


def _append_trailer(content: str, label: str, value: str) -> str:
    # Ensure there is exactly one blank line before trailers if typical style
    if not content.endswith("\n"):
        content += "\n"
    # If there is no blank line at end, add one more
    if not content.endswith("\n\n"):
        content += "\n"
    return content + f"{label}: {value}\n"


def _collect_files_payload() -> List[Dict]:
    name_status = _get_name_status()
    numstat = _get_numstat()
    payload = []
    for status, path, old in name_status:
        stats = numstat.get(path, {"additions": 0, "deletions": 0})
        payload.append({
            "path": path,
            "old_path": old,
            "status": status,
            "additions": stats.get("additions", 0),
            "deletions": stats.get("deletions", 0)
        })
    return payload


def _first_meaningful_line(message: str) -> str:
    for line in message.splitlines():
        if not line.strip():
            continue
        if line.lstrip().startswith('#'):
            continue
        return line.strip()
    return ""


def _call_service(message: str, files_payload: List[Dict]) -> str:
    import requests
    url = SERVICE_URL.rstrip('/') + "/explain-change"
    resp = requests.post(url, json={"message": message, "files": files_payload}, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    return data.get("explanation") or "Update codebase."


def _local_explain(message: str, files_payload: List[Dict]) -> str:
    try:
        from src.explain import generate_explanation
    except Exception:
        # Fallback if import fails
        def generate_explanation(message=None, files=None, diff=None):
            subject = _first_meaningful_line(message)
            subject = subject.rstrip('.') if subject else "Update codebase"
            return f"{subject} across {len(files or [])} file(s)."
    return generate_explanation(message=message, files=files_payload)


def main():
    if len(sys.argv) < 2:
        sys.exit(0)

    commit_msg_path = sys.argv[1]
    try:
        content = _read_commit_message(commit_msg_path)
    except Exception:
        sys.exit(0)

    # Only act on AI-generated commits
    if not _has_truthy_trailer(content, AI_TRAILER_LABEL):
        sys.exit(0)

    # Avoid duplicating the explanation
    if _has_trailer(content, EXPLAIN_TRAILER_LABEL):
        sys.exit(0)

    # Prepare payload
    try:
        files_payload = _collect_files_payload()
    except Exception:
        files_payload = []

    # Explanation
    try:
        if SERVICE_URL:
            explanation = _call_service(content, files_payload)
        else:
            explanation = _local_explain(content, files_payload)
    except Exception:
        # As a last resort, create a minimal rationale
        subject = _first_meaningful_line(content) or "Update codebase"
        explanation = f"{subject.rstrip('.')} across {len(files_payload)} file(s)."

    # Append trailer
    updated = _append_trailer(content, EXPLAIN_TRAILER_LABEL, explanation)

    try:
        _write_commit_message(commit_msg_path, updated)
    except Exception:
        # If write fails, do not block commit; exit gracefully
        pass

if __name__ == "__main__":
    main()

