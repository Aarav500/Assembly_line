#!/usr/bin/env python3
import os
import sys
import subprocess
from typing import List

# Ensure local imports work when run as hook
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from secret_scanner import SecretScanner  # noqa: E402


def get_staged_files() -> List[str]:
    try:
        out = subprocess.check_output(["git", "diff", "--cached", "--name-only"], stderr=subprocess.DEVNULL)
        return [l for l in out.decode().splitlines() if l.strip()]
    except Exception:
        return []


def get_staged_content(path: str) -> str:
    try:
        out = subprocess.check_output(["git", "show", f":{path}"])
        return out.decode(errors='replace')
    except Exception:
        return ""


def main() -> int:
    if os.environ.get("SECRET_SCAN_SKIP") == "1":
        print("[secret-scan] Skipping scan due to SECRET_SCAN_SKIP=1", file=sys.stderr)
        return 0

    base = os.getcwd()
    scanner = SecretScanner()
    files = get_staged_files()
    total_findings = []

    for rel in files:
        absf = os.path.join(base, rel)
        if os.path.exists(absf) and os.path.getsize(absf) > scanner.max_file_size:
            continue
        # Best-effort text detection
        if os.path.exists(absf) and not scanner._is_text_file(absf):
            continue
        content = get_staged_content(rel)
        if not content:
            continue
        total_findings.extend(scanner._scan_content(content, rel))

    if total_findings:
        print("[secret-scan] Potential secrets detected in staged changes:", file=sys.stderr)
        for f in total_findings[:500]:
            loc = f"{f['file']}:{f['line']}:{f['col']}"
            rule = f.get('rule')
            match = f.get('match')
            ent = f.get('entropy')
            ent_s = f" entropy={ent}" if ent is not None else ""
            print(f" - {loc} [{rule}]{ent_s} -> {match}", file=sys.stderr)
        print("\nRemediation tips:", file=sys.stderr)
        print(" - Remove the secret from the code or replace with a secure reference (e.g., env var).", file=sys.stderr)
        print(" - If this is a false positive, adjust patterns or add exclusions.", file=sys.stderr)
        print(" - After fixing, re-stage changes and commit again.", file=sys.stderr)

        if os.environ.get("ALLOW_SECRETS") == "1":
            print("[secret-scan] ALLOW_SECRETS=1 set; allowing commit despite findings.", file=sys.stderr)
            return 0
        return 1

    print("[secret-scan] No secrets detected in staged changes.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

