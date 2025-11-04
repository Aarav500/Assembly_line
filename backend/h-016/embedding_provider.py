import os
import numpy as np


class EmbeddingProvider:
    def __init__(self):
        self.use_openai = os.getenv("USE_OPENAI", "0") == "1" or bool(os.getenv("OPENAI_API_KEY"))
        self.default_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        self._openai = None
        if self.use_openai:
            try:
                from openai import OpenAI
                self._openai = OpenAI()
            except Exception:
                # fallback to fake if import fails
                self.use_openai = False
                self._openai = None

    def _fake_embed(self, text: str, dim: int = 256):
        # deterministic pseudo-embedding from text
        rng = np.random.default_rng(abs(hash(text)) % (2**32))
        vec = rng.normal(0, 1, dim)
        # L2 normalize
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.astype(float).tolist()

    def generate_embedding(self, text: str, model: str = None):
        model = model or self.default_model
        if not self.use_openai or self._openai is None:
            return self._fake_embed(text)
        try:
            resp = self._openai.embeddings.create(
                model=model,
                input=text,
            )
            # newest openai client returns .data[0].embedding
            return resp.data[0].embedding
        except Exception:
            # fallback to fake on any provider error
            return self._fake_embed(text)

