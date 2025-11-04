import os
import glob
import pickle
from typing import List, Dict, Any
from dataclasses import dataclass
from sklearn.feature_extraction.text import TfidfVectorizer
from scipy import sparse


def _read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def _normalize_whitespace(s: str) -> str:
    return " ".join(s.replace("\r", " ").replace("\n", " ").split())


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    words = text.split()
    if not words:
        return []
    stride = max(1, chunk_size - chunk_overlap)
    chunks = []
    for start in range(0, len(words), stride):
        end = min(start + chunk_size, len(words))
        if end - start <= 0:
            break
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end == len(words):
            break
    return chunks


@dataclass
class Chunk:
    id: str
    source: str
    position: int
    text: str


class CorpusIndex:
    def __init__(self, data_dir: str = "data", storage_dir: str = "storage", chunk_size: int = 180, chunk_overlap: int = 40):
        self.data_dir = data_dir
        self.storage_dir = storage_dir
        self.index_path = os.path.join(self.storage_dir, "index.pkl")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        self.vectorizer: TfidfVectorizer = None
        self.matrix: sparse.spmatrix = None
        self.chunks: List[Chunk] = []
        self.files_indexed: List[str] = []

    def has_index(self) -> bool:
        return os.path.exists(self.index_path)

    def load_documents(self) -> List[Dict[str, Any]]:
        patterns = [os.path.join(self.data_dir, "**/*.txt"), os.path.join(self.data_dir, "*.txt")]
        files = []
        for p in patterns:
            files.extend(glob.glob(p, recursive=True))
        files = sorted(list(set(files)))

        documents = []
        for fp in files:
            try:
                text = _read_text_file(fp)
                documents.append({"path": fp, "text": text})
            except Exception:
                continue
        return documents

    def build_index(self):
        os.makedirs(self.storage_dir, exist_ok=True)
        documents = self.load_documents()
        chunks: List[Chunk] = []
        for doc in documents:
            raw_text = doc["text"]
            norm = _normalize_whitespace(raw_text)
            parts = chunk_text(norm, self.chunk_size, self.chunk_overlap)
            for i, p in enumerate(parts):
                chunk_id = f"{os.path.basename(doc['path'])}::chunk_{i}"
                chunks.append(Chunk(id=chunk_id, source=os.path.relpath(doc["path"], self.data_dir), position=i, text=p))
        self.chunks = chunks
        self.files_indexed = [d["path"] for d in documents]

        # Build TF-IDF index
        texts = [c.text for c in self.chunks]
        if not texts:
            # Create an empty placeholder index
            self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words='english', norm='l2')
            self.matrix = sparse.csr_matrix((0, 0))
        else:
            self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words='english', norm='l2', max_df=0.95)
            self.matrix = self.vectorizer.fit_transform(texts)

        payload = {
            "vectorizer": self.vectorizer,
            "matrix": self.matrix,
            "chunks": self.chunks,
            "meta": {
                "chunk_size": self.chunk_size,
                "chunk_overlap": self.chunk_overlap,
                "files_indexed": self.files_indexed,
                "num_chunks": len(self.chunks),
            }
        }
        with open(self.index_path, "wb") as f:
            pickle.dump(payload, f)

    def load_index(self):
        if not self.has_index():
            raise FileNotFoundError("Index file not found. Build it first.")
        with open(self.index_path, "rb") as f:
            payload = pickle.load(f)
        self.vectorizer = payload.get("vectorizer")
        self.matrix = payload.get("matrix")
        self.chunks = payload.get("chunks", [])
        meta = payload.get("meta", {})
        self.chunk_size = meta.get("chunk_size", self.chunk_size)
        self.chunk_overlap = meta.get("chunk_overlap", self.chunk_overlap)
        self.files_indexed = meta.get("files_indexed", [])

    def index_info(self) -> Dict[str, Any]:
        return {
            "data_dir": self.data_dir,
            "storage_dir": self.storage_dir,
            "index_path": self.index_path,
            "files_indexed": [os.path.relpath(f, self.data_dir) for f in self.files_indexed],
            "num_chunks": len(self.chunks),
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
        }

