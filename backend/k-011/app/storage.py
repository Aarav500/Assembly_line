import json
import os
from threading import Lock
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from .models import Proposal, ProposalStatus


class JSONFileStore:
    def __init__(self, path: str, default_data):
        self.path = path
        self._lock = Lock()
        self._default = default_data
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._default, f, indent=2)

    def read(self) -> Any:
        with self._lock:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)

    def write(self, data: Any):
        with self._lock:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)


class ItemsStore:
    def __init__(self, data_dir: str):
        self.store = JSONFileStore(os.path.join(data_dir, "items.json"), {"items": {}})

    def list_items(self) -> Dict[str, Dict]:
        data = self.store.read()
        return data.get("items", {})

    def get_item(self, item_id: str) -> Optional[Dict]:
        return self.list_items().get(item_id)

    def upsert_item(self, item_id: str, item: Dict):
        data = self.store.read()
        items = data.get("items", {})
        items[item_id] = item
        data["items"] = items
        self.store.write(data)

    def snapshot_item(self, item_id: str) -> Optional[Dict]:
        item = self.get_item(item_id)
        return json.loads(json.dumps(item)) if item is not None else None


class ProposalStore:
    def __init__(self, data_dir: str):
        self.store = JSONFileStore(os.path.join(data_dir, "proposals.json"), {"proposals": []})

    def list(self) -> List[Dict]:
        return self.store.read().get("proposals", [])

    def get(self, proposal_id: str) -> Optional[Dict]:
        for p in self.list():
            if p.get("id") == proposal_id:
                return p
        return None

    def add(self, proposal: Proposal) -> Dict:
        data = self.store.read()
        proposals = data.get("proposals", [])
        proposals.append(proposal.to_dict())
        data["proposals"] = proposals
        self.store.write(data)
        return proposal.to_dict()

    def update(self, proposal_id: str, **updates) -> Optional[Dict]:
        data = self.store.read()
        proposals = data.get("proposals", [])
        updated = None
        for p in proposals:
            if p.get("id") == proposal_id:
                p.update(updates)
                p["updated_at"] = datetime.now(timezone.utc).isoformat()
                updated = p
                break
        if updated is not None:
            data["proposals"] = proposals
            self.store.write(data)
        return updated


class AppRepositories:
    def __init__(self, data_dir: str):
        self.items = ItemsStore(data_dir)
        self.proposals = ProposalStore(data_dir)

