from typing import Dict, List, Optional, Any
from threading import RLock


class InMemoryStore:
    def __init__(self) -> None:
        self._data: Dict[str, Dict[str, List[Any]]] = {}
        self._lock = RLock()

    def store_dataset(self, dataset_id: str, metrics: Dict[str, List[Any]]) -> None:
        with self._lock:
            self._data[dataset_id] = metrics

    def get_dataset(self, dataset_id: str) -> Optional[Dict[str, List[Any]]]:
        with self._lock:
            return self._data.get(dataset_id)

    def list_ids(self):
        with self._lock:
            return sorted(list(self._data.keys()))

