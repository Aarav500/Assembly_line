from typing import Dict, List
from services.index import PatentIndex
from utils.text import tokenize_simple


def score_novelty(index: PatentIndex, query_text: str, top_k: int = 5) -> Dict:
    """
    Returns a dict with fields:
      - novelty_score: float (0..1, higher is more novel)
      - max_similarity: float
      - avg_topk_similarity: float
      - coverage: float (0..1 of query token overlap with union of top-k neighbors)
      - neighbors: list of {id, similarity, overlap_terms, text_preview, meta}
    """
    neighbors = index.search(query_text, top_k=top_k)
    if not neighbors:
        return {
            "novelty_score": 1.0,
            "max_similarity": 0.0,
            "avg_topk_similarity": 0.0,
            "coverage": 0.0,
            "uniqueness": 1.0,
            "neighbors": [],
        }

    sims = [n.get("similarity", 0.0) for n in neighbors]
    max_sim = max(sims) if sims else 0.0
    avg_sim = sum(sims) / len(sims) if sims else 0.0

    # Token coverage against union of top-k docs
    query_tokens = set(tokenize_simple(query_text))
    union_tokens = set()
    for n in neighbors:
        # derive tokens from preview (already normalized by index)
        text_prev = n.get("text_preview") or ""
        union_tokens.update(tokenize_simple(text_prev))
    overlap = query_tokens.intersection(union_tokens)
    coverage = (len(overlap) / max(1, len(query_tokens))) if query_tokens else 0.0
    uniqueness = 1.0 - coverage

    # Combine signals: emphasize max_sim as strong prior-art signal, tempered by uniqueness
    novelty_from_similarity = 1.0 - max_sim
    novelty_score = max(0.0, min(1.0, 0.6 * novelty_from_similarity + 0.4 * uniqueness))

    return {
        "novelty_score": round(novelty_score, 6),
        "max_similarity": round(max_sim, 6),
        "avg_topk_similarity": round(avg_sim, 6),
        "coverage": round(coverage, 6),
        "uniqueness": round(uniqueness, 6),
        "neighbors": neighbors,
    }

