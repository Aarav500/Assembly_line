import threading
from typing import List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer


class EmbeddingService:
    def __init__(self, model_name: str, device: str = "cpu", normalize_default: bool = True):
        self.model_name = model_name
        self.device = device
        self.normalize_default = normalize_default
        self._model_lock = threading.Lock()
        self._model: Optional[SentenceTransformer] = None
        # Eager load to get dimension
        _ = self.model
        self._dimension = self._model.get_sentence_embedding_dimension()

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            with self._model_lock:
                if self._model is None:
                    self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: List[str], normalize: Optional[bool] = None) -> List[List[float]]:
        if normalize is None:
            normalize = self.normalize_default
        embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False, normalize_embeddings=False)
        if normalize:
            embeddings = self._l2_normalize(embeddings)
        return embeddings.astype(float).tolist()

    @staticmethod
    def _l2_normalize(x: np.ndarray, eps: float = 1e-12) -> np.ndarray:
        norms = np.linalg.norm(x, axis=1, keepdims=True)
        norms = np.maximum(norms, eps)
        return x / norms

