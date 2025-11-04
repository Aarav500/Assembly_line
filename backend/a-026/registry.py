import os
import json
import uuid
from typing import List, Dict, Any


class ProjectRegistry:
    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        os.makedirs(os.path.dirname(storage_path), exist_ok=True)
        self._data = {"projects": []}
        self._load()

    def _load(self):
        if os.path.isfile(self.storage_path):
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
                if 'projects' not in self._data:
                    self._data['projects'] = []
            except Exception:
                self._data = {"projects": []}

    def _save(self):
        tmp = self.storage_path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(self._data, f, indent=2)
        os.replace(tmp, self.storage_path)

    def list_projects(self) -> List[Dict[str, Any]]:
        return list(self._data.get('projects', []))

    def add_project(self, name: str, path: str) -> Dict[str, Any]:
        path = os.path.abspath(path)
        if not os.path.isdir(path):
            raise FileNotFoundError(f"Path does not exist: {path}")
        # prevent duplicates by path
        for p in self._data['projects']:
            if os.path.abspath(p['path']) == path:
                raise ValueError("Project with this path already registered")
        proj = {
            'id': uuid.uuid4().hex,
            'name': name,
            'path': path,
        }
        self._data['projects'].append(proj)
        self._save()
        return proj

    def remove_project(self, project_id: str):
        before = len(self._data['projects'])
        self._data['projects'] = [p for p in self._data['projects'] if p['id'] != project_id]
        after = len(self._data['projects'])
        if before == after:
            raise KeyError("not found")
        self._save()

