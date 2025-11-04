import os
import json
import threading
from typing import Dict, Any, Optional, List


class BuildStorage:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump({'builds': []}, f)

    def _read(self) -> Dict[str, Any]:
        with self._lock:
            with open(self.path, 'r', encoding='utf-8') as f:
                return json.load(f)

    def _write(self, data: Dict[str, Any]):
        with self._lock:
            tmp = self.path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, self.path)

    def list_builds(self) -> List[Dict[str, Any]]:
        data = self._read()
        return data.get('builds', [])

    def get_build(self, build_id: str) -> Optional[Dict[str, Any]]:
        data = self._read()
        for b in data.get('builds', []):
            if b.get('id') == build_id:
                return b
        return None

    def save_build(self, build_id: str, build: Dict[str, Any]):
        data = self._read()
        builds = data.get('builds', [])
        replaced = False
        for i, b in enumerate(builds):
            if b.get('id') == build_id:
                builds[i] = build
                replaced = True
                break
        if not replaced:
            builds.append(build)
        data['builds'] = builds
        self._write(data)

