from typing import List, Dict, Tuple, Set
import math

COMPLEXITY_KEYWORDS = {
    "ml": 4.0,
    "machine learning": 4.5,
    "ai": 3.5,
    "nlp": 3.5,
    "mobile": 2.5,
    "ios": 2.5,
    "android": 2.5,
    "realtime": 3.0,
    "real-time": 3.0,
    "websocket": 3.0,
    "search": 2.0,
    "payments": 3.0,
    "pci": 3.5,
    "oauth": 2.0,
    "auth": 2.0,
    "authentication": 2.0,
    "authorization": 2.0,
    "billing": 2.5,
    "reporting": 1.5,
    "analytics": 2.0,
    "recommendation": 3.5,
    "map": 2.0,
    "geolocation": 2.0,
    "sync": 2.0,
    "offline": 2.5,
    "encryption": 2.5,
    "security": 2.5,
    "scalability": 2.0,
    "kpi": 1.0,
    "export": 1.0,
}

RISK_KEYWORDS = {
    "unknown": 2.5,
    "new tech": 2.0,
    "integration": 2.0,
    "dependency": 1.5,
    "third-party": 2.0,
    "beta": 1.5,
    "compliance": 2.5,
    "security": 2.0,
    "payments": 2.5,
    "ml": 2.0,
}


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def safe_div(a: float, b: float, default: float = 0.0) -> float:
    try:
        if b == 0:
            return default
        return a / b
    except Exception:
        return default


def estimate_effort(description: str) -> float:
    desc = (description or "").lower()
    base = 2.0  # baseline person-days
    bonus = 0.0
    for k, w in COMPLEXITY_KEYWORDS.items():
        if k in desc:
            bonus += w
    # description length as minor proxy
    bonus += min(len(desc) / 500.0, 2.0)
    return max(1.0, base + bonus)


def estimate_risk(description: str) -> float:
    desc = (description or "").lower()
    base = 2.0
    for k, w in RISK_KEYWORDS.items():
        if k in desc:
            base += w
    return max(0.5, min(10.0, base))


def normalize(values: List[float]) -> List[float]:
    if not values:
        return []
    mn = min(values)
    mx = max(values)
    if math.isclose(mx, mn):
        return [0.5 for _ in values]
    return [(v - mn) / (mx - mn) for v in values]


def topo_sort(nodes: List[str], edges: Dict[str, List[str]]) -> Tuple[List[str], List[List[str]]]:
    # Kahn's algorithm; detect cycles
    from collections import deque, defaultdict
    indeg = {n: 0 for n in nodes}
    adj = defaultdict(list)
    for n in nodes:
        for dep in edges.get(n, []):
            if dep not in indeg:
                indeg[dep] = 0
            adj[dep].append(n)
            indeg[n] += 1
    q = deque([n for n, d in indeg.items() if d == 0])
    order = []
    while q:
        u = q.popleft()
        order.append(u)
        for v in adj.get(u, []):
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    cycles = []
    if len(order) < len(indeg):
        # Extract cycles roughly: nodes with indegree>0
        cyc_nodes = [n for n, d in indeg.items() if d > 0]
        cycles.append(cyc_nodes)
    return order, cycles


def dependency_closure(start: str, edges: Dict[str, List[str]]) -> List[str]:
    seen: Set[str] = set()
    stack = [start]
    order: List[str] = []
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        order.append(n)
        for d in edges.get(n, []):
            if d not in seen:
                stack.append(d)
    # deps first
    order = list(dict.fromkeys(reversed(order)))
    return [x for x in order if x != start] + [start]

