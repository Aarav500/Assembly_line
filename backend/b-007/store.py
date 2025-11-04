import json
import os
import threading
import time
import uuid
from typing import List, Optional, Dict, Any

import numpy as np


class ItemStore:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self._lock = threading.Lock()
        self._items: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        if not os.path.exists(self.filepath):
            self._items = []
            return
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                items = data.get('items', []) if isinstance(data, dict) else data
                # basic validation
                self._items = [self._sanitize_loaded_item(x) for x in items]
        except Exception:
            self._items = []

    def _sanitize_loaded_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        item = dict(item)
        item['id'] = item.get('id') or str(uuid.uuid4())
        item['type'] = (item.get('type') or '').strip().lower()
        item['title'] = item.get('title') or ''
        item['content'] = item.get('content') or ''
        emb = item.get('embedding') or []
        # Ensure embedding is list of floats
        item['embedding'] = [float(x) for x in emb]
        item['created_at'] = item.get('created_at') or time.time()
        return item

    def _save(self):
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        tmp = {
            'items': self._items,
            'count': len(self._items),
            'updated_at': time.time(),
        }
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(tmp, f, ensure_ascii=False)

    def add_item(self, item_type: str, title: str, content: str, embedding: np.ndarray) -> Dict[str, Any]:
        with self._lock:
            item = {
                'id': str(uuid.uuid4()),
                'type': item_type,
                'title': title,
                'content': content,
                'embedding': [float(x) for x in embedding.tolist()],
                'created_at': time.time(),
            }
            self._items.append(item)
            self._save()
            return item

    def list_items(self, item_type: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            if not item_type:
                return list(self._items)
            t = item_type.strip().lower()
            return [x for x in self._items if x.get('type') == t]

    def delete_item(self, item_id: str) -> bool:
        with self._lock:
            n_before = len(self._items)
            self._items = [x for x in self._items if x.get('id') != item_id]
            if len(self._items) != n_before:
                self._save()
                return True
            return False

    def search(self, query_vec: np.ndarray, item_type: Optional[str] = None, top_k: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            items = self._items if not item_type else [x for x in self._items if x.get('type') == item_type]
            if not items:
                return []
            # Prepare matrix of embeddings
            # Embeddings are stored normalized; dot product equals cosine similarity
            embs = np.array([x['embedding'] for x in items], dtype=np.float32)
            q = np.asarray(query_vec, dtype=np.float32)
            # normalize query to be safe
            q_norm = q / max(np.linalg.norm(q), 1e-12)
            scores = embs @ q_norm
            top_k = max(1, min(top_k, len(items)))
            idxs = np.argpartition(-scores, top_k - 1)[:top_k]
            # Sort by score desc
            idxs = idxs[np.argsort(-scores[idxs])]
            results = []
            for idx in idxs:
                it = items[idx]
                results.append({
                    'id': it['id'],
                    'type': it['type'],
                    'title': it['title'],
                    'content': it['content'],
                    'score': float(scores[idx]),
                    'created_at': it.get('created_at'),
                })
            return results

