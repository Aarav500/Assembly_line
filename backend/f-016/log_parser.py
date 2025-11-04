import os
import re
import json
from datetime import datetime
from typing import List, Dict, Any

# Default patterns and status map
DEFAULT_PATTERNS = [
    {
        "name": "generic_test_line",
        "regex": r"(?i)\bTEST(?:CASE)?[:\s]+(?P<test>[A-Za-z0-9_.\-/:\[\]<>]+)\s+(?P<status>PASS|PASSED|FAIL|FAILED|ERROR|SKIP|SKIPPED)(?:\s+seed[=:](?P<seed>\S+))?(?:.*?\bcmd[=:](?P<cmd>.+))?",
        "status_map": {
            "PASS": "PASS", "PASSED": "PASS",
            "FAIL": "FAIL", "FAILED": "FAIL",
            "ERROR": "ERROR",
            "SKIP": "SKIP", "SKIPPED": "SKIP"
        }
    },
    {
        "name": "pytest_summary_line",
        "regex": r"(?P<test>[A-Za-z0-9_\./\[\]:]+)\s+(?P<status>PASSED|FAILED|ERROR|SKIPPED|XPASS|XFAIL)",
        "status_map": {
            "PASSED": "PASS",
            "FAILED": "FAIL",
            "ERROR": "ERROR",
            "SKIPPED": "SKIP",
            "XFAIL": "PASS",
            "XPASS": "FAIL"
        }
    },
    {
        "name": "unittest_nose_line",
        "regex": r"(?i)\b(?P<status>ok|FAIL|ERROR|skipped)\b[:\s-]+(?P<test>[A-Za-z0-9_.:/\[\]-]+)",
        "status_map": {
            "ok": "PASS",
            "FAIL": "FAIL",
            "ERROR": "ERROR",
            "skipped": "SKIP"
        }
    }
]

TIMESTAMP_REGEXES = [
    re.compile(r"(?P<ts>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)"),
    re.compile(r"(?P<ts>\d{2}:\d{2}:\d{2}(?:\.\d+)?)")
]

_compiled_patterns = None


def _load_patterns():
    global _compiled_patterns
    if _compiled_patterns is not None:
        return _compiled_patterns
    patterns = []
    cfg_path = os.path.join('config', 'patterns.json')
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            for p in cfg.get('patterns', []):
                patterns.append({
                    'name': p.get('name', 'unnamed'),
                    'regex': re.compile(p['regex']),
                    'status_map': p.get('status_map', {})
                })
        except Exception:
            pass
    if not patterns:
        for p in DEFAULT_PATTERNS:
            patterns.append({
                'name': p['name'],
                'regex': re.compile(p['regex']),
                'status_map': p['status_map']
            })
    _compiled_patterns = patterns
    return _compiled_patterns


def _normalize_status(raw: str, status_map: Dict[str, str]) -> str:
    if raw is None:
        return 'UNKNOWN'
    return status_map.get(raw, status_map.get(raw.upper(), raw.upper()))


def _extract_timestamp(line: str):
    for rx in TIMESTAMP_REGEXES:
        m = rx.search(line)
        if m:
            ts = m.group('ts')
            # Try parse
            try:
                if 'T' in ts or '-' in ts:
                    dt = datetime.fromisoformat(ts.replace('Z',''))
                else:
                    today = datetime.utcnow().date().isoformat()
                    dt = datetime.fromisoformat(f"{today}T{ts}")
                return dt.isoformat() + 'Z'
            except Exception:
                return None
    return None


def parse_text(text: str, source: str = 'unknown') -> List[Dict[str, Any]]:
    patterns = _load_patterns()
    lines = text.splitlines()
    results = []
    for line in lines:
        for p in patterns:
            m = p['regex'].search(line)
            if not m:
                continue
            gd = m.groupdict()
            raw_status = gd.get('status')
            status = _normalize_status(raw_status, p['status_map'])
            test_name = gd.get('test')
            seed = gd.get('seed')
            cmd = gd.get('cmd')
            if seed is None:
                m_seed = re.search(r"\bseed[=:]([^\s]+)", line, flags=re.IGNORECASE)
                if m_seed:
                    seed = m_seed.group(1)
            if cmd is None:
                m_cmd = re.search(r"\bcmd[=:](.+)$", line)
                if m_cmd:
                    cmd = m_cmd.group(1).strip()
            ts = _extract_timestamp(line)
            results.append({
                'test_name': test_name,
                'status': status,
                'raw_status': raw_status,
                'timestamp': ts,
                'seed': seed,
                'cmd': cmd,
                'env': None,
                'source': source
            })
            break
    return [r for r in results if r.get('test_name') and r.get('status')]


def parse_file(path: str) -> List[Dict[str, Any]]:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
    except UnicodeDecodeError:
        with open(path, 'r', encoding='latin-1', errors='ignore') as f:
            text = f.read()
    return parse_text(text, source=path)

