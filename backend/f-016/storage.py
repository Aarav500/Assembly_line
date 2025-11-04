import os
import json
import threading
import hashlib
from datetime import datetime
from typing import List, Dict, Any

DATA_DIR = 'data'
DB_PATH = os.path.join(DATA_DIR, 'db.json')
_lock = threading.Lock()


def ensure_data_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DB_PATH):
        with open(DB_PATH, 'w', encoding='utf-8') as f:
            json.dump({"runs": []}, f)


def _load_db() -> Dict[str, Any]:
    ensure_data_dirs()
    with open(DB_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def _save_db(db: Dict[str, Any]):
    with open(DB_PATH, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=2)


def _fingerprint(run: Dict[str, Any]) -> str:
    s = json.dumps({k: run.get(k) for k in ['test_name','status','timestamp','seed','cmd','source']}, sort_keys=True)
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def add_runs(runs: List[Dict[str, Any]]) -> int:
    stored = 0
    with _lock:
        db = _load_db()
        existing = set(r.get('fp') for r in db.get('runs', []) if r.get('fp'))
        for r in runs:
            r = dict(r)
            if not r.get('timestamp'):
                r['timestamp'] = datetime.utcnow().isoformat() + 'Z'
            r['fp'] = _fingerprint(r)
            if r['fp'] in existing:
                continue
            db['runs'].append(r)
            existing.add(r['fp'])
            stored += 1
        _save_db(db)
    return stored


def aggregate_tests() -> Dict[str, Dict[str, Any]]:
    with _lock:
        db = _load_db()
    agg: Dict[str, Dict[str, Any]] = {}
    for r in db.get('runs', []):
        name = r['test_name']
        if name not in agg:
            agg[name] = {
                'counts': {'PASS': 0, 'FAIL': 0, 'ERROR': 0, 'SKIP': 0},
                'statuses': set(),
                'runs': []
            }
        norm = r.get('status', 'UNKNOWN')
        if norm not in agg[name]['counts']:
            agg[name]['counts'][norm] = 0
        agg[name]['counts'][norm] += 1
        agg[name]['statuses'].add(norm)
        agg[name]['runs'].append(r)
    return agg

