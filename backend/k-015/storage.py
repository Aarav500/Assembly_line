import json
import os
import threading
import uuid
from datetime import datetime
from typing import Dict, List, Optional


class Storage:
    def __init__(self, path: str = 'data/runs.json'):
        self.path = path
        self._lock = threading.Lock()
        self._ensure_dirs()
        self._data = self._load()

    def _ensure_dirs(self):
        d = os.path.dirname(self.path)
        if d and not os.path.exists(d):
            os.makedirs(d, exist_ok=True)

    def _load(self) -> Dict:
        if not os.path.exists(self.path):
            return {"runs": {}}
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {"runs": {}}

    def _save(self):
        tmp_path = self.path + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self.path)

    def create_run(self, params: Dict) -> Dict:
        with self._lock:
            run_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat() + 'Z'
            run = {
                'id': run_id,
                'created_at': now,
                'updated_at': now,
                'status': 'pending',
                'initial_prompt': params.get('initial_prompt', ''),
                'current_prompt': params.get('current_prompt', params.get('initial_prompt', '')),
                'criteria': params.get('criteria', []),
                'target_score': float(params.get('target_score', 0.9)),
                'max_iterations': int(params.get('max_iterations', 5)),
                'model': params.get('model', 'dummy'),
                'temperature': float(params.get('temperature', 0.2)),
                'iterations': []
            }
            self._data['runs'][run_id] = run
            self._save()
            return run

    def get_run(self, run_id: str) -> Optional[Dict]:
        with self._lock:
            run = self._data['runs'].get(run_id)
            return json.loads(json.dumps(run)) if run else None

    def update_run(self, run: Dict) -> Dict:
        with self._lock:
            run['updated_at'] = datetime.utcnow().isoformat() + 'Z'
            self._data['runs'][run['id']] = run
            self._save()
            return run

    def list_runs(self) -> List[Dict]:
        with self._lock:
            return list(self._data['runs'].values())

