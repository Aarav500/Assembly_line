from typing import Dict, List, Tuple, Optional
import time

from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np
from scipy import sparse

from utils.text import normalize_text


class PatentIndex:
    def __init__(self, name: str):
        self.name = name
        self._docs: Dict[str, Dict] = {}
        self._order: List[str] = []
        self._X = None  # sparse matrix
        self._vectorizer: Optional[TfidfVectorizer] = None
        self._last_fit = 0.0

    def add_documents(self, documents: List[Dict]) -> Tuple[int, int]:
        """
        documents: list of {id: str, text: str, meta?: any}
        Returns: (added_count, total_count)
        """
        added = 0
        for d in documents:
            doc_id = str(d.get("id")) if d.get("id") is not None else None
            text = d.get("text")
            if not doc_id or not text:
                continue
            text_norm = normalize_text(text)
            if doc_id not in self._docs:
                self._order.append(doc_id)
                added += 1
            self._docs[doc_id] = {"id": doc_id, "text": text_norm, "meta": d.get("meta")}
        self._fit()
        return added, len(self._docs)

    def _fit(self):
        corpus = [self._docs[i]["text"] for i in self._order]
        if not corpus:
            self._X = None
            self._vectorizer = None
            return
        self._vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            ngram_range=(1, 2),
            max_df=0.9,
            min_df=1,
            sublinear_tf=True,
            norm="l2",
        )
        self._X = self._vectorizer.fit_transform(corpus)
        self._last_fit = time.time()

    def count(self) -> int:
        return len(self._docs)

    def vocabulary_size(self) -> int:
        if self._vectorizer is None:
            return 0
        try:
            return len(self._vectorizer.vocabulary_)
        except Exception:
            return 0

    def _ensure_ready(self):
        if self._vectorizer is None or self._X is None:
            self._fit()

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        self._ensure_ready()
        if self._vectorizer is None or self._X is None or self._X.shape[0] == 0:
            return []
        q_vec = self._vectorizer.transform([normalize_text(query)])  # l2 normalized
        # cosine similarity via dot product (since vectors are l2-normalized)
        sims = self._X.dot(q_vec.T).toarray().ravel()
        if sims.size == 0:
            return []
        top_k = max(1, int(top_k))
        idxs = np.argpartition(-sims, range(min(top_k, sims.shape[0])))[:top_k]
        idxs = idxs[np.argsort(-sims[idxs])]
        results = []
        feature_names = self._vectorizer.get_feature_names_out()
        q_nonzero = q_vec.nonzero()[1]
        q_weights = q_vec.toarray().ravel()
        q_weights_map = {int(i): float(q_weights[i]) for i in q_nonzero}
        for i in idxs:
            doc_id = self._order[int(i)]
            doc = self._docs[doc_id]
            sim = float(sims[i])
            # overlap terms
            d_vec = self._X[i]
            d_idx = set(d_vec.nonzero()[1].tolist())
            overlap_idx = [j for j in q_nonzero if j in d_idx]
            # top overlapping by query weight
            overlap_idx_sorted = sorted(overlap_idx, key=lambda j: -q_weights_map.get(int(j), 0.0))[:10]
            overlap_terms = [str(feature_names[j]) for j in overlap_idx_sorted]
            preview = doc["text"][:240].strip()
            results.append({
                "id": doc_id,
                "similarity": round(sim, 6),
                "overlap_terms": overlap_terms,
                "text_preview": preview,
                "meta": doc.get("meta"),
            })
        return results

    def doc_token_set(self, doc_id: str) -> set:
        doc = self._docs.get(doc_id)
        if not doc:
            return set()
        text = doc.get("text") or ""
        tokens = set((text or "").split())
        return tokens


class IndexRegistry:
    def __init__(self):
        self._indexes: Dict[str, PatentIndex] = {}

    def create_index(self, name: str) -> PatentIndex:
        name = str(name)
        if name in self._indexes:
            return self._indexes[name]
        idx = PatentIndex(name)
        self._indexes[name] = idx
        return idx

    def get_index(self, name: str) -> Optional[PatentIndex]:
        return self._indexes.get(str(name))

    def delete_index(self, name: str) -> bool:
        name = str(name)
        if name in self._indexes:
            del self._indexes[name]
            return True
        return False

    def list_indexes(self) -> List[str]:
        return sorted(list(self._indexes.keys()))

