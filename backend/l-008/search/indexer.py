import os
import json
import numpy as np
from typing import List, Dict, Optional, Any
from joblib import dump, load
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from .models import Document
from .ranking import combine_scores
from config import (
    DATA_DIR,
    DOCS_PATH,
    TFIDF_PATH,
    EMB_PATH,
    META_PATH,
    EMBEDDING_MODEL_NAME,
    DISABLE_EMBEDDINGS,
    NGRAM_RANGE,
    MIN_DF,
    MAX_FEATURES,
    STOP_WORDS,
)

class Indexer:
    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.docs: List[Document] = []
        self.id_to_idx: Dict[str, int] = {}
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.tfidf_matrix = None  # scipy sparse
        self.emb_model = None
        self.embeddings: Optional[np.ndarray] = None
        self.emb_ready = False
        self.meta: Dict[str, Any] = {}

    def load(self):
        # Load docs
        if os.path.exists(DOCS_PATH):
            with open(DOCS_PATH, "r", encoding="utf-8") as f:
                self.docs = [Document.from_payload(json.loads(line)) for line in f]
            self._rebuild_id_index()
        # Load TF-IDF
        if os.path.exists(TFIDF_PATH):
            try:
                obj = load(TFIDF_PATH)
                self.vectorizer = obj["vectorizer"]
                self.tfidf_matrix = obj["matrix"]
            except Exception:
                self.vectorizer = None
                self.tfidf_matrix = None
        # Load embeddings
        if os.path.exists(EMB_PATH):
            try:
                self.embeddings = np.load(EMB_PATH)
            except Exception:
                self.embeddings = None
        # Load meta
        if os.path.exists(META_PATH):
            try:
                with open(META_PATH, "r", encoding="utf-8") as f:
                    self.meta = json.load(f)
            except Exception:
                self.meta = {}
        self._maybe_load_embedding_model()
        # Validate sizes
        if self.embeddings is not None and self.embeddings.shape[0] != len(self.docs):
            # size mismatch; rebuild later
            self.embeddings = None
            self.emb_ready = False
        else:
            self.emb_ready = self.embeddings is not None

    def save(self):
        # Save docs
        with open(DOCS_PATH, "w", encoding="utf-8") as f:
            for d in self.docs:
                f.write(json.dumps(d.to_dict(), ensure_ascii=False) + "\n")
        # Save TF-IDF
        if self.vectorizer is not None and self.tfidf_matrix is not None:
            dump({"vectorizer": self.vectorizer, "matrix": self.tfidf_matrix}, TFIDF_PATH)
        # Save embeddings
        if self.embeddings is not None:
            np.save(EMB_PATH, self.embeddings)
        # Save meta
        with open(META_PATH, "w", encoding="utf-8") as f:
            json.dump(self.meta, f)

    def _rebuild_id_index(self):
        self.id_to_idx = {d.id: i for i, d in enumerate(self.docs)}

    def _maybe_load_embedding_model(self):
        if DISABLE_EMBEDDINGS:
            self.emb_model = None
            self.emb_ready = False
            return
        try:
            from sentence_transformers import SentenceTransformer
            if self.emb_model is None:
                self.emb_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        except Exception:
            self.emb_model = None
            self.emb_ready = False

    def clear(self):
        self.docs = []
        self._rebuild_id_index()
        self.vectorizer = None
        self.tfidf_matrix = None
        self.embeddings = None
        self.emb_ready = False
        self.meta = {}
        for p in [DOCS_PATH, TFIDF_PATH, EMB_PATH, META_PATH]:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass

    def add_documents(self, items: List[Dict[str, Any]]) -> int:
        added = 0
        for it in items:
            doc = Document.from_payload(it)
            if not doc.content:
                continue
            self.docs.append(doc)
            added += 1
        if added:
            self._rebuild_id_index()
        return added

    def rebuild_lexical(self):
        if not self.docs:
            self.vectorizer = None
            self.tfidf_matrix = None
            return
        texts = [d.content for d in self.docs]
        vec = TfidfVectorizer(
            analyzer="word",
            ngram_range=NGRAM_RANGE,
            min_df=MIN_DF,
            max_features=MAX_FEATURES,
            stop_words=STOP_WORDS,
        )
        self.tfidf_matrix = vec.fit_transform(texts)
        self.vectorizer = vec

    def ensure_embeddings(self, new_only: bool = False):
        self._maybe_load_embedding_model()
        if self.emb_model is None:
            self.embeddings = None
            self.emb_ready = False
            return
        if not self.docs:
            self.embeddings = None
            self.emb_ready = False
            return
        if self.embeddings is None or not new_only:
            texts = [d.content for d in self.docs]
            mat = self.emb_model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
            self.embeddings = mat
            self.emb_ready = True
        else:
            # Append only for new docs
            cur_n = self.embeddings.shape[0]
            if cur_n < len(self.docs):
                new_texts = [d.content for d in self.docs[cur_n:]]
                mat = self.emb_model.encode(new_texts, convert_to_numpy=True, normalize_embeddings=True)
                self.embeddings = np.vstack([self.embeddings, mat])
                self.emb_ready = True

    def _lexical_scores(self, query: str, mask: Optional[np.ndarray]) -> Optional[np.ndarray]:
        if self.vectorizer is None or self.tfidf_matrix is None or not self.docs:
            return None
        qv = self.vectorizer.transform([query])
        sims = cosine_similarity(qv, self.tfidf_matrix)[0]
        if mask is not None:
            sims = sims * mask
        return sims

    def _semantic_scores(self, query: str, mask: Optional[np.ndarray]) -> Optional[np.ndarray]:
        if not self.emb_ready or self.embeddings is None or self.embeddings.shape[0] == 0:
            return None
        if self.emb_model is None:
            return None
        qv = self.emb_model.encode([query], convert_to_numpy=True, normalize_embeddings=True)[0]
        sims = np.dot(self.embeddings, qv)
        if mask is not None:
            sims = sims * mask
        return sims

    def _make_mask(self, source_types: Optional[List[str]]) -> Optional[np.ndarray]:
        if not source_types:
            return None
        stypes = set([s.lower() for s in source_types])
        mask = np.array([1.0 if (d.source_type in stypes) else 0.0 for d in self.docs], dtype=float)
        return mask

    def search(
        self,
        query: str,
        top_k: int = 10,
        mode: str = "hybrid",
        w_lex: float = 0.5,
        w_sem: float = 0.5,
        source_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        if not self.docs:
            return {"query": query, "total": 0, "results": []}

        mode = (mode or "hybrid").lower()
        mask = self._make_mask(source_types)

        lex_scores = self._lexical_scores(query, mask) if mode in ("lexical", "hybrid") else None
        sem_scores = self._semantic_scores(query, mask) if mode in ("semantic", "hybrid") else None

        if mode == "lexical" and lex_scores is None:
            # Fall back to semantic
            lex_scores = None
            sem_scores = self._semantic_scores(query, mask)
        if mode == "semantic" and sem_scores is None:
            # Fall back to lexical
            sem_scores = None
            lex_scores = self._lexical_scores(query, mask)

        combo, lex_scaled, sem_scaled = combine_scores(lex_scores, sem_scores, w_lex=w_lex, w_sem=w_sem)
        if combo.size == 0:
            # No scoring available
            return {"query": query, "total": 0, "results": []}

        order = np.argsort(-combo)
        top_k = max(1, min(top_k, len(self.docs)))
        top_idx = order[:top_k]

        results = []
        for i in top_idx:
            d = self.docs[int(i)]
            results.append({
                "id": d.id,
                "title": d.title,
                "path": d.path,
                "source_type": d.source_type,
                "tags": d.tags,
                "scores": {
                    "combined": float(combo[i]),
                    "lexical": float(lex_scaled[i]) if lex_scores is not None else None,
                    "semantic": float(sem_scaled[i]) if sem_scores is not None else None,
                },
                "snippet": self._make_snippet(d, query),
            })

        return {
            "query": query,
            "total": len(self.docs),
            "mode": mode,
            "weights": {"lexical": w_lex, "semantic": w_sem},
            "filtered_types": source_types or [],
            "results": results,
        }

    def _make_snippet(self, d: Document, query: str, max_len: int = 240) -> str:
        text = d.content
        if not text:
            return ""
        q = query.strip().split()
        pos = -1
        for term in q:
            p = text.lower().find(term.lower())
            if p >= 0:
                pos = p
                break
        if pos < 0:
            return text[:max_len]
        start = max(0, pos - max_len // 4)
        end = min(len(text), start + max_len)
        snippet = text[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."
        return snippet

    def get_doc(self, doc_id: str) -> Optional[Dict[str, Any]]:
        idx = self.id_to_idx.get(doc_id)
        if idx is None:
            return None
        return self.docs[idx].to_dict()

    def stats(self) -> Dict[str, Any]:
        by_type: Dict[str, int] = {}
        for d in self.docs:
            by_type[d.source_type] = by_type.get(d.source_type, 0) + 1
        return {
            "total_docs": len(self.docs),
            "by_type": by_type,
            "embeddings_ready": self.emb_ready,
            "embedding_model": EMBEDDING_MODEL_NAME if self.emb_model is not None else None,
            "lexical_ready": self.vectorizer is not None and self.tfidf_matrix is not None,
        }

