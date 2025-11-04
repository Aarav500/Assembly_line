import re
from typing import Any, Dict, List, Optional
from .graph_store import GraphStore


class QueryEngine:
    def __init__(self, store: GraphStore):
        self.store = store

    def execute(self, query: str) -> Dict[str, Any]:
        q = (query or '').strip()
        ql = q.lower()

        # Path between A and B
        m = re.search(r"path\s+between\s+['\"]?(.+?)['\"]?\s+and\s+['\"]?(.+?)['\"]?", ql)
        if m:
            a_name, b_name = m.group(1), m.group(2)
            return self._path_between(a_name, b_name)

        # Dependencies of X
        m = re.search(r"(dependencies|depends)\s+of\s+['\"]?(.+?)['\"]?$", ql)
        if m:
            x = m.group(2)
            return self._edges_for(x, label='DEPENDS_ON', direction='out')
        m = re.search(r"what\s+does\s+['\"]?(.+?)['\"]?\s+depend\s+on", ql)
        if m:
            x = m.group(1)
            return self._edges_for(x, label='DEPENDS_ON', direction='out')

        # Who calls X / What does X call
        m = re.search(r"who\s+calls\s+['\"]?(.+?)['\"]?", ql)
        if m:
            x = m.group(1)
            return self._edges_for(x, label='CALLS', direction='in')
        m = re.search(r"what\s+does\s+['\"]?(.+?)['\"]?\s+call", ql)
        if m:
            x = m.group(1)
            return self._edges_for(x, label='CALLS', direction='out')

        # Imports of artifact X
        m = re.search(r"imports\s+of\s+['\"]?(.+?)['\"]?", ql)
        if m:
            x = m.group(1)
            return self._edges_for(x, label='IMPORTS', direction='out', any_type=True)

        # Mentions of X
        m = re.search(r"mentions\s+of\s+['\"]?(.+?)['\"]?", ql)
        if m:
            x = m.group(1)
            return self._edges_for(x, label='MENTIONS', direction='in', any_type=True)

        # Find node by name
        m = re.search(r"find\s+['\"]?(.+?)['\"]?$", ql)
        if m:
            x = m.group(1)
            return {
                "query": q,
                "matched_nodes": self.store.search_nodes(x)
            }

        # default: search
        return {
            "query": q,
            "matched_nodes": self.store.search_nodes(q)
        }

    def _path_between(self, a_name: str, b_name: str) -> Dict[str, Any]:
        aid = self._find_any(a_name)
        bid = self._find_any(b_name)
        if not aid or not bid:
            return {"error": "one or both nodes not found", "a": a_name, "b": b_name}
        path = self.store.path_bfs(aid, bid, max_depth=6)
        return {
            "a": self.store.get_node(aid),
            "b": self.store.get_node(bid),
            "path": [self.store.get_node(n) for n in path],
            "edges": [e for e in self.store.edges.values() if e['source'] in path and e['target'] in path]
        }

    def _edges_for(self, name: str, label: str, direction: str, any_type: bool = False) -> Dict[str, Any]:
        nid = self._find_any(name)
        if not nid:
            return {"error": f"node not found: {name}"}
        neighbors = self.store.neighbors(nid, direction='out' if direction=='out' else 'in', label=label)
        node = self.store.get_node(nid)
        nodes = [self.store.get_node(x[0]) for x in neighbors]
        edges = [x[1] for x in neighbors]
        return {
            "node": node,
            "label": label,
            "direction": direction,
            "nodes": nodes,
            "edges": edges
        }

    def _find_any(self, name: str) -> Optional[str]:
        # try exact across types first
        nid = self.store.find_node_id(name)
        if nid:
            return nid
        # fallback: prefix search
        cands = self.store.search_nodes(name)
        return cands[0]['id'] if cands else None

