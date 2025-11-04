import threading
import numpy as np
from sentence_transformers import SentenceTransformer


class EmbeddingService:
    _model = None
    _lock = threading.Lock()

    def __init__(self, model_name: str = 'sentence-transformers/all-MiniLM-L6-v2'):
        # Lazy-load model once
        with EmbeddingService._lock:
            if EmbeddingService._model is None:
                EmbeddingService._model = SentenceTransformer(model_name)
        self.model = EmbeddingService._model

    def embed(self, text: str) -> np.ndarray:
        vec = self.model.encode([text], normalize_embeddings=True)[0]
        # Ensure it's a 1D numpy array float32
        return np.asarray(vec, dtype=np.float32)

