import json
import os
import threading
import hashlib
import time
from typing import Dict, Any, List, Optional, Tuple


def _slugify(text: str) -> str:
    allowed = "abcdefghijklmnopqrstuvwxyz0123456789-_"
    text = (text or "").lower()
    text = ''.join(ch if ch.isalnum() else '-' for ch in text)
    text = '-'.join([t for t in text.split('-') if t])
    if not text:
        text = 'x'
    text = ''.join(ch for ch in text if ch in allowed)
    return text[:64]


def _norm_key(name: str, type_: str) -> str:
    return f"{(type_ or '').strip().lower()}::{(name or '').strip().lower()}"


class GraphStore:
    def __init__(self):
        self._lock = threading.Lock()
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: Dict[str, Dict[str, Any]] = {}
        self._index: Dict[str, str] = {}  # norm_key -> node_id

    # Node ops
    def upsert_node(self, name: str, type_: str, properties: Optional[Dict[str, Any]] = None) -> str:
        if name is None:
            name = ""
        if type_ is None:
            type_ = "ENTITY"
        key = _norm_key(name, type_)
        with self._lock:
            node_id = self._index.get(key)
            if node_id is None:
                base = f"{type_}-{_slugify(name)}"
                digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]
                node_id = f"{base}-{digest}"
                self.nodes[node_id] = {
                    "id": node_id,
                    "name": name,
                    "type": type_.upper(),
                    "properties": {},
                    "created_at": time.time()
                }
                self._index[key] = node_id
            if properties:
                # Merge shallowly
                self.nodes[node_id]["properties"].update(properties)
            return node_id

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        return self.nodes.get(node_id)

    def find_node_id(self, name: str, type_: Optional[str] = None) -> Optional[str]:
        if type_:
            return self._index.get(_norm_key(name, type_))
        # Search across types if not specified
        name_l = (name or '').strip().lower()
        for nid, n in self.nodes.items():
            if n.get('name', '').strip().lower() == name_l:
                return nid
        return None

    def search_nodes(self, query: str, type_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        q = (query or '').strip().lower()
        results = []
        for n in self.nodes.values():
            if type_filter and n.get('type') != type_filter.upper():
                continue
            if not q or q in n.get('name', '').lower() or q in (n.get('type', '') or '').lower():
                results.append(n)
        # Simple ranking: startswith first, then contains
        def rank(n):
            name = n.get('name','').lower()
            if name.startswith(q):
                return (0, len(name))
            return (1, len(name))
        results.sort(key=rank)
        return results[:200]

    # Edge ops
    def _edge_key(self, src: str, dst: str, label: str) -> str:
        base = f"{src}|{label.upper()}|{dst}"
        return hashlib.sha1(base.encode('utf-8')).hexdigest()

    def add_edge(self, source: str, target: str, label: str, properties: Optional[Dict[str, Any]] = None) -> str:
        if not source or not target or not label:
            raise ValueError("source, target, label required")
        with self._lock:
            ek = self._edge_key(source, target, label)
            if ek not in self.edges:
                self.edges[ek] = {
                    "id": ek,
                    "source": source,
                    "target": target,
                    "label": label.upper(),
                    "properties": properties or {},
                    "created_at": time.time()
                }
            else:
                if properties:
                    self.edges[ek]["properties"].update(properties)
            return ek

    def neighbors(self, node_id: str, direction: str = 'out', label: Optional[str] = None) -> List[Tuple[str, Dict[str, Any]]]:
        results = []
        for e in self.edges.values():
            if direction in ('out', 'both') and e['source'] == node_id:
                if not label or e['label'] == label.upper():
                    results.append((e['target'], e))
            if direction in ('in', 'both') and e['target'] == node_id:
                if not label or e['label'] == label.upper():
                    results.append((e['source'], e))
        return results

    def path_bfs(self, start_id: str, end_id: str, max_depth: int = 5) -> List[str]:
        if start_id == end_id:
            return [start_id]
        visited = set([start_id])
        from collections import deque
        q = deque()
        q.append((start_id, [start_id]))
        depth = {start_id: 0}
        while q:
            cur, path = q.popleft()
            if depth[cur] >= max_depth:
                continue
            for nid, _ in self.neighbors(cur, direction='both'):
                if nid in visited:
                    continue
                visited.add(nid)
                new_path = path + [nid]
                if nid == end_id:
                    return new_path
                depth[nid] = depth[cur] + 1
                q.append((nid, new_path))
        return []

    # Persistence
    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": list(self.nodes.values()),
            "edges": list(self.edges.values())
        }

    def save(self, path: str):
        tmp = path + ".tmp"
        with self._lock:
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)

    def load(self, path: str):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        with self._lock:
            self.nodes = {n['id']: n for n in data.get('nodes', [])}
            self.edges = {e['id']: e for e in data.get('edges', [])}
            # rebuild index
            self._index.clear()
            for nid, n in self.nodes.items():
                key = _norm_key(n.get('name', ''), n.get('type', ''))
                self._index[key] = nid

    def clear(self):
        with self._lock:
            self.nodes.clear()
            self.edges.clear()
            self._index.clear()

    # Utilities for artifact handling
    def ensure_artifact(self, artifact_id: str, artifact_type: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        props = {"artifact_id": artifact_id}
        if metadata:
            props.update({f"meta.{k}": v for k, v in metadata.items()})
        return self.upsert_node(name=artifact_id, type_="ARTIFACT", properties=props)

