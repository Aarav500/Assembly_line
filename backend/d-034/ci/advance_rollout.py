import json
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import yaml
import requests
from dateutil import parser, tz


GITHUB_OUTPUT = os.environ.get('GITHUB_OUTPUT')


def write_output(key: str, value: str) -> None:
    # Write both to GITHUB_OUTPUT (for Actions) and stdout for other CIs
    line = f"{key}={value}\n"
    if GITHUB_OUTPUT:
        with open(GITHUB_OUTPUT, 'a', encoding='utf-8') as f:
            f.write(line)
    # Also print for visibility
    print(f"::set-output name={key}::{value}")


def iso_utc(dt: datetime) -> str:
    if dt.tzinfo is not None:
        dt = dt.astimezone(tz.UTC).replace(tzinfo=None)
    return dt.isoformat(timespec='seconds') + 'Z'


def now_utc() -> datetime:
    return datetime.utcnow()


def parse_iso_utc(s: str) -> datetime:
    dt = parser.isoparse(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz.UTC)
    return dt.astimezone(tz.UTC).replace(tzinfo=None)


def from_service() -> Optional[Dict[str, Any]]:
    api = os.environ.get('API_URL', '').strip()
    token = os.environ.get('CI_AUTH_TOKEN') or os.environ.get('AUTH_TOKEN')
    if not api:
        return None
    try:
        r = requests.get(f"{api.rstrip('/')}/api/ci/ready", params={'limit': 1}, headers={'Authorization': f'Bearer {token}'} if token else None, timeout=20)
        r.raise_for_status()
        data = r.json()
        tasks = data.get('tasks') or []
        if not tasks:
            return {'deploy': False, 'reason': 'no_ready_tasks', 'source': 'service', 'now': data.get('now_utc')}
        t = tasks[0]
        return {
            'deploy': True,
            'source': 'service',
            'stage_id': t.get('stage_id'),
            'release_name': t.get('release_name'),
            'version': t.get('version'),
            'stage_name': t.get('stage_name'),
            'target': t.get('target') or (str(t.get('percentage')) + '%'),
            'start_at': t.get('start_at'),
            'end_at': t.get('end_at'),
        }
    except Exception as e:
        print(f"[warn] failed contacting rollout service: {e}")
        return None


def from_yaml() -> Dict[str, Any]:
    path = os.environ.get('ROLLOUTS_FILE', 'rollouts.yaml')
    window_min = int(os.environ.get('TRIGGER_WINDOW_MINUTES', '10'))
    now = now_utc()

    if not os.path.exists(path):
        return {'deploy': False, 'reason': f'missing_file:{path}', 'source': 'yaml', 'now': iso_utc(now)}

    with open(path, 'r', encoding='utf-8') as f:
        try:
            cfg = yaml.safe_load(f) or {}
        except Exception as e:
            return {'deploy': False, 'reason': f'invalid_yaml:{e}', 'source': 'yaml', 'now': iso_utc(now)}

    releases: List[Dict[str, Any]] = (cfg.get('releases') or [])
    candidates: List[Dict[str, Any]] = []
    for rel in releases:
        rname = rel.get('name')
        version = rel.get('version')
        if not rname or not version:
            continue
        for st in (rel.get('stages') or []):
            if 'start_at' not in st:
                continue
            try:
                st_start = parse_iso_utc(st['start_at'])
            except Exception:
                continue
            # Select within window
            if 0 <= (now - st_start).total_seconds() <= window_min * 60:
                candidates.append({
                    'release_name': rname,
                    'version': version,
                    'stage_name': st.get('name') or 'stage',
                    'target': st.get('target') or (str(st.get('percentage')) + '%'),
                    'start_at': iso_utc(st_start),
                    'end_at': st.get('end_at'),
                })

    if not candidates:
        return {'deploy': False, 'reason': 'no_stage_in_window', 'source': 'yaml', 'now': iso_utc(now)}

    # Pick the earliest start in window (deterministic)
    candidates.sort(key=lambda x: x['start_at'])
    c = candidates[0]
    c.update({'deploy': True, 'source': 'yaml'})
    return c


def main() -> int:
    result = from_service()
    if result is None:
        result = from_yaml()

    print("Rollout decision:")
    print(json.dumps(result, indent=2))

    write_output('deploy', 'true' if result.get('deploy') else 'false')
    write_output('source', str(result.get('source', 'unknown')))
    write_output('release_name', str(result.get('release_name', '')))
    write_output('version', str(result.get('version', '')))
    write_output('stage_name', str(result.get('stage_name', '')))
    write_output('target', str(result.get('target', '')))
    if result.get('stage_id') is not None:
        write_output('stage_id', str(result.get('stage_id')))

    return 0


if __name__ == '__main__':
    sys.exit(main())

