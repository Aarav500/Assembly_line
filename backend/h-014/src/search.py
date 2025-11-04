import os
from typing import List, Dict, Any
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize
import numpy as np
import joblib
import config


class SearchEngine:
    def __init__(self, index_path: str | None = None):
        self.vectorizer: TfidfVectorizer | None = None
        self.matrix = None
        self.documents: List[Dict[str, Any]] = []
        self.index_path = index_path or config.INDEX_FILE

    def build(self, documents: List[Dict]):
        self.documents = documents
        corpus = [d.get('content', '') for d in documents]
        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words='english',
            ngram_range=(1, 2),
            max_df=0.9,
            min_df=1
        )
        self.matrix = self.vectorizer.fit_transform(corpus)
        # Ensure L2 normalized (TF-IDF usually is already)
        self.matrix = normalize(self.matrix, norm='l2', copy=False)

    def query(self, q: str, top_k: int = 8) -> List[Dict]:
        if self.vectorizer is None or self.matrix is None or not self.documents:
            return []
        q_vec = self.vectorizer.transform([q])
        q_vec = normalize(q_vec, norm='l2', copy=False)
        sims = (self.matrix @ q_vec.T).toarray().ravel()
        if sims.size == 0:
            return []
        idx = np.argsort(-sims)[:max(1, top_k)]
        results: List[Dict] = []
        for i in idx:
            d = self.documents[int(i)]
            results.append({
                'id': d.get('id'),
                'score': float(sims[i]),
                'type': d.get('type'),
                'title': d.get('title'),
                'source_file': d.get('source_file'),
                'language': d.get('language'),
                'content': d.get('content')
            })
        return results

    def save(self):
        if self.vectorizer is None or self.matrix is None:
            return
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        payload = {
            'vectorizer': self.vectorizer,
            'matrix': self.matrix,
            'documents': self.documents,
        }
        joblib.dump(payload, self.index_path)

    def load(self) -> bool:
        if not os.path.exists(self.index_path):
            return False
        try:
            payload = joblib.load(self.index_path)
            self.vectorizer = payload.get('vectorizer')
            self.matrix = payload.get('matrix')
            self.documents = payload.get('documents', [])
            return True
        except Exception:
            return False

    def num_documents(self) -> int:
        return len(self.documents)

    def get_kb_items(self) -> List[Dict]:
        items: List[Dict] = []
        for d in self.documents:
            items.append({
                'id': d.get('id'),
                'type': d.get('type'),
                'title': d.get('title'),
                'source_file': d.get('source_file'),
                'language': d.get('language'),
                'excerpt': (d.get('content') or '')[:300]
            })
        return items

    def reset(self):
        self.vectorizer = None
        self.matrix = None
        self.documents = []

