from typing import List, Dict, Any
import numpy as np
from scipy import sparse
from .indexer import CorpusIndex


class Retriever:
    def __init__(self, corpus_index: CorpusIndex):
        self.index = corpus_index

    def top_k(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        if self.index.matrix is None or self.index.vectorizer is None or len(self.index.chunks) == 0:
            return []

        q_vec = self.index.vectorizer.transform([query])  # shape (1, n_features)
        # cosine similarity since TF-IDF is L2-normalized
        sims = self.index.matrix.dot(q_vec.T)  # shape (num_chunks, 1)
        if sparse.issparse(sims):
            sims = sims.toarray()
        sims = sims.reshape(-1)

        k = max(1, min(k, len(self.index.chunks)))
        top_idx = np.argpartition(-sims, k - 1)[:k]
        # sort by score descending
        top_idx = top_idx[np.argsort(-sims[top_idx])]

        results: List[Dict[str, Any]] = []
        for idx in top_idx:
            ch = self.index.chunks[idx]
            results.append({
                "id": ch.id,
                "source": ch.source,
                "position": ch.position,
                "text": ch.text,
                "score": float(sims[idx])
            })
        return results

