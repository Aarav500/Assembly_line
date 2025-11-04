import json
import os
import threading

class State:
    def __init__(self, path):
        self.path = path
        self._lock = threading.RLock()
        self._data = {"clusters": {}}
        self._loaded = False
        self._ensure_loaded()

    def _ensure_loaded(self):
        with self._lock:
            if self._loaded:
                return
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            if os.path.exists(self.path):
                try:
                    with open(self.path, 'r') as f:
                        self._data = json.load(f)
                        if not isinstance(self._data, dict):
                            self._data = {"clusters": {}}
                except Exception:
                    self._data = {"clusters": {}}
            else:
                self._data = {"clusters": {}}
            self._loaded = True

    def save(self):
        with self._lock:
            tmp = self.path + ".tmp"
            with open(tmp, 'w') as f:
                json.dump(self._data, f, indent=2)
            os.replace(tmp, self.path)

    def get(self):
        with self._lock:
            return json.loads(json.dumps(self._data))

    def get_cluster(self, name):
        with self._lock:
            return json.loads(json.dumps(self._data.get("clusters", {}).get(name)))

    def set_cluster(self, name, cluster):
        with self._lock:
            self._data.setdefault("clusters", {})[name] = cluster
            self.save()

    def delete_cluster(self, name):
        with self._lock:
            if name in self._data.get("clusters", {}):
                del self._data["clusters"][name]
                self.save()
            else:
                raise FileNotFoundError("cluster not found")

    def list_clusters(self):
        with self._lock:
            return list(self._data.get("clusters", {}).keys())

