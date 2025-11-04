from __future__ import annotations
from typing import Iterable, Tuple


def jaccard_similarity(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if inter == 0:
        return 0.0
    union = len(a | b)
    return inter / union if union else 0.0


def top_pairwise_similar(items: list[Tuple[int, int, set[str]]], threshold: float = 0.6, limit: int = 1000) -> list[Tuple[int, int, float]]:
    # items: (function_id, project_id, shingles)
    # naive O(n^2) pairwise; acceptable for small/medium datasets
    n = len(items)
    pairs: list[Tuple[int, int, float]] = []
    for i in range(n):
        fid_i, pid_i, sh_i = items[i]
        for j in range(i+1, n):
            fid_j, pid_j, sh_j = items[j]
            if pid_i == pid_j:
                continue  # cross-project only
            score = jaccard_similarity(sh_i, sh_j)
            if score >= threshold:
                pairs.append((fid_i, fid_j, float(f"{score:.4f}")))
                if len(pairs) >= limit:
                    return pairs
    # sort by score descending
    pairs.sort(key=lambda x: x[2], reverse=True)
    return pairs[:limit]

