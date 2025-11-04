import glob
import os
import re
import unicodedata
from dataclasses import dataclass
from typing import List, Dict, Any

from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np


@dataclass
class DocumentChunk:
    id: int
    text: str
    path: str


def normalize_ws(text: str) -> str:
    # Normalize unicode and whitespace for consistent comparisons
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def split_into_chunks(text: str, max_chars: int = 800, overlap: int = 80) -> List[str]:
    # Split by blank lines into paragraphs, then pack into chunks
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks = []
    current = ""
    for p in paragraphs:
        if not current:
            current = p
            continue
        if len(current) + 1 + len(p) <= max_chars:
            current = current + "\n" + p
        else:
            # finalize current
            chunks.append(current)
            # prepare next with overlap
            if overlap > 0 and len(current) > overlap:
                start_overlap = max(0, len(current) - overlap)
                prefix = current[start_overlap:]
                current = prefix + "\n" + p
            else:
                current = p
    if current:
        chunks.append(current)

    # If any chunk is too long (single very long paragraph), hard wrap
    final_chunks = []
    for ch in chunks:
        if len(ch) <= max_chars:
            final_chunks.append(ch)
        else:
            # hard split by sentence or char window
            sentences = re.split(r"(?<=[.!?])\s+", ch)
            buf = ""
            for s in sentences:
                if not buf:
                    buf = s
                elif len(buf) + 1 + len(s) <= max_chars:
                    buf += " " + s
                else:
                    final_chunks.append(buf)
                    if overlap > 0 and len(buf) > overlap:
                        tail = buf[-overlap:]
                        buf = tail + " " + s
                    else:
                        buf = s
            if buf:
                final_chunks.append(buf)
    return final_chunks


class DocumentStore:
    def __init__(self, docs_glob: str, include_exts: set, max_chars: int, overlap: int):
        self.docs_glob = docs_glob
        self.include_exts = include_exts
        self.max_chars = max_chars
        self.overlap = overlap
        self.chunks: List[DocumentChunk] = []

    def load(self) -> List[DocumentChunk]:
        paths = [p for p in glob.glob(self.docs_glob, recursive=True) if os.path.isfile(p)]
        chunks: List[DocumentChunk] = []
        idx = 0
        for p in sorted(paths):
            ext = os.path.splitext(p)[1].lower()
            if self.include_exts and ext not in self.include_exts:
                continue
            try:
                with open(p, "r", encoding="utf-8") as f:
                    raw = f.read()
            except Exception:
                # Try latin-1 as fallback
                try:
                    with open(p, "r", encoding="latin-1") as f:
                        raw = f.read()
                except Exception:
                    continue
            # Strip front-matter if present
            raw = re.sub(r"^---[\s\S]*?---\s*", "", raw)
            # Remove code blocks to avoid noise
            raw_clean = re.sub(r"```[\s\S]*?```", "", raw)
            for ch in split_into_chunks(raw_clean, self.max_chars, self.overlap):
                chunks.append(DocumentChunk(id=idx, text=ch, path=p))
                idx += 1
        self.chunks = chunks
        return chunks


class TfidfRetriever:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
        self.doc_matrix = None

    def fit(self, texts: List[str]):
        self.doc_matrix = self.vectorizer.fit_transform(texts)

    def query(self, question: str) -> np.ndarray:
        q_vec = self.vectorizer.transform([question])
        # cosine similarity since tfidf vectors are L2-normalized
        sims = (self.doc_matrix @ q_vec.T).toarray().ravel()
        return sims


class QAEngine:
    def __init__(self, docs_glob: str, include_exts: set, max_chars: int, overlap: int):
        self.store = DocumentStore(docs_glob, include_exts, max_chars, overlap)
        self.retriever = TfidfRetriever()
        self._loaded = False

    def load(self):
        chunks = self.store.load()
        texts = [c.text for c in chunks]
        if not texts:
            self.retriever.fit([""])
        else:
            self.retriever.fit(texts)
        self._loaded = True

    def answer(self, question: str, top_k: int = 3) -> Dict[str, Any]:
        if not self._loaded:
            self.load()
        sims = self.retriever.query(question)
        if sims.size == 0:
            return {"answer": "", "contexts": []}
        order = np.argsort(-sims)
        k = int(top_k) if top_k and top_k > 0 else 3
        k = min(k, len(order))
        results = []
        for i in range(k):
            idx = int(order[i])
            ch = self.store.chunks[idx]
            score = float(sims[idx])
            results.append({
                "text": ch.text,
                "score": score,
                "source": ch.path,
                "chunk_id": ch.id
            })
        best_answer = results[0]["text"] if results else ""
        return {"answer": best_answer, "contexts": results}

    def stats(self) -> Dict[str, Any]:
        return {"chunks": len(self.store.chunks)}

