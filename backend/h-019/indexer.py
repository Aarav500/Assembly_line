import os
import re
import json
from typing import List, Dict, Optional, Iterable
from datetime import datetime

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from scipy import sparse
import joblib

ALLOWED_EXTS = {
    ".py", ".md", ".txt", ".rst", ".json", ".yml", ".yaml", ".ini", ".cfg", ".conf", ".toml",
    ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rb", ".php", ".cs", ".swift", ".kt", ".kts",
    ".scala", ".rs", ".c", ".h", ".hpp", ".cc", ".cpp", ".m", ".mm", ".sh", ".bat"
}

DEFAULT_EXCLUDES = [
    "**/.git/**",
    "**/.svn/**",
    "**/.hg/**",
    "**/node_modules/**",
    "**/.venv/**",
    "**/venv/**",
    "**/dist/**",
    "**/build/**",
    "**/__pycache__/**",
]

SENTENCE_SPLIT_RE = re.compile(r"(?<=[\.!?])\s+")


def glob_match(path: str, patterns: Iterable[str]) -> bool:
    import fnmatch
    for pat in patterns:
        if fnmatch.fnmatch(path, pat) or fnmatch.fnmatch(path.replace("\\", "/"), pat):
            return True
    return False


def iter_files(root_dir: str, include_globs: Optional[List[str]] = None, exclude_globs: Optional[List[str]] = None) -> Iterable[str]:
    exclude = set(DEFAULT_EXCLUDES)
    if exclude_globs:
        exclude.update(exclude_globs)
    for dirpath, dirnames, filenames in os.walk(root_dir):
        norm_dir = dirpath.replace("\\", "/")
        # Prune excluded directories eagerly
        pruned = []
        for d in list(dirnames):
            full = os.path.join(dirpath, d)
            full_norm = full.replace("\\", "/")
            if glob_match(full_norm + "/", exclude):
                pruned.append(d)
        for d in pruned:
            dirnames.remove(d)

        for fn in filenames:
            path = os.path.join(dirpath, fn)
            norm = path.replace("\\", "/")
            if include_globs and not glob_match(norm, include_globs):
                # If includes are specified, only allow matches
                continue
            ext = os.path.splitext(fn)[1].lower()
            if not include_globs and ext not in ALLOWED_EXTS:
                continue
            if glob_match(norm, exclude):
                continue
            try:
                if os.path.getsize(path) > 2 * 1024 * 1024:  # skip files > 2MB
                    continue
            except OSError:
                continue
            yield path


def read_text_file(path: str) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return None


def chunk_lines(lines: List[str], chunk_size: int = 40, overlap: int = 10) -> List[Dict]:
    chunks = []
    n = len(lines)
    i = 0
    chunk_id = 0
    while i < n:
        start = i
        end = min(i + chunk_size, n)
        text = "".join(lines[start:end]).strip()
        if text:
            chunks.append({
                "id": chunk_id,
                "start_line": start + 1,
                "end_line": end,
                "text": text,
            })
            chunk_id += 1
        if end >= n:
            break
        i = end - overlap
    return chunks


class KnowledgeIndex:
    def __init__(self, index_dir: str = "index_data"):
        self.index_dir = index_dir
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.matrix = None  # scipy sparse matrix
        self.meta: List[Dict] = []

    def _paths(self) -> Dict[str, str]:
        return {
            "vectorizer": os.path.join(self.index_dir, "vectorizer.joblib"),
            "matrix": os.path.join(self.index_dir, "matrix.npz"),
            "meta": os.path.join(self.index_dir, "meta.json"),
            "manifest": os.path.join(self.index_dir, "manifest.json"),
        }

    def is_built(self) -> bool:
        p = self._paths()
        return os.path.exists(p["vectorizer"]) and os.path.exists(p["matrix"]) and os.path.exists(p["meta"]) \
            and os.path.exists(p["manifest"])  # ensure complete

    def build(self, root_dir: str, include_globs: Optional[List[str]] = None, exclude_globs: Optional[List[str]] = None) -> Dict:
        os.makedirs(self.index_dir, exist_ok=True)
        texts = []
        meta = []
        total_files = 0
        total_chunks = 0

        for path in iter_files(root_dir, include_globs, exclude_globs):
            text = read_text_file(path)
            if text is None:
                continue
            total_files += 1
            lines = text.splitlines(keepends=True)
            chunks = chunk_lines(lines)
            for c in chunks:
                texts.append(c["text"])  # content
                meta.append({
                    "file": os.path.relpath(path, root_dir),
                    "abs_path": os.path.abspath(path),
                    "start_line": c["start_line"],
                    "end_line": c["end_line"],
                })
            total_chunks += len(chunks)

        if not texts:
            raise RuntimeError("No indexable content found.")

        vectorizer = TfidfVectorizer(
            input="content",
            lowercase=True,
            stop_words="english",
            ngram_range=(1, 2),
            max_features=200_000,
            norm="l2"
        )
        X = vectorizer.fit_transform(texts)

        # Save artifacts
        paths = self._paths()
        joblib.dump(vectorizer, paths["vectorizer"])  # vectorizer
        sparse.save_npz(paths["matrix"], X)  # matrix
        with open(paths["meta"], "w", encoding="utf-8") as f:
            json.dump(meta, f)
        manifest = {
            "root_dir": os.path.abspath(root_dir),
            "built_at": datetime.utcnow().isoformat() + "Z",
            "num_files": total_files,
            "num_chunks": total_chunks,
            "index_version": 1
        }
        with open(paths["manifest"], "w", encoding="utf-8") as f:
            json.dump(manifest, f)

        # Load into memory
        self.vectorizer = vectorizer
        self.matrix = X
        self.meta = meta

        return manifest

    def _ensure_loaded(self):
        if self.vectorizer is not None and self.matrix is not None and self.meta:
            return
        if not self.is_built():
            raise RuntimeError("Index not built.")
        paths = self._paths()
        self.vectorizer = joblib.load(paths["vectorizer"])  # type: ignore
        self.matrix = sparse.load_npz(paths["matrix"])  # type: ignore
        with open(paths["meta"], "r", encoding="utf-8") as f:
            self.meta = json.load(f)

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        self._ensure_loaded()
        q_vec = self.vectorizer.transform([query])  # shape (1, d)
        # cosine similarity because TF-IDF vectors are L2-normalized
        sims = self.matrix.dot(q_vec.T).toarray().ravel()  # shape (n_chunks,)
        if sims.size == 0:
            return []
        top_k = max(1, min(int(top_k), sims.shape[0]))
        idx = np.argpartition(-sims, top_k - 1)[:top_k]
        idx_sorted = idx[np.argsort(-sims[idx])]
        results = []
        for i in idx_sorted:
            m = self.meta[i]
            score = float(sims[i])
            # Extract a snippet around the chunk's first lines for readability
            snippet = self._get_snippet_for_index(i)
            results.append({
                "file": m["file"],
                "abs_path": m.get("abs_path"),
                "start_line": m["start_line"],
                "end_line": m["end_line"],
                "score": round(score, 4),
                "snippet": snippet
            })
        return results

    def _get_snippet_for_index(self, idx: int, max_chars: int = 600) -> str:
        # Recreate text from TF-IDF feature space is not possible; instead, reload relevant section from disk
        # We'll read the file and slice lines
        m = self.meta[idx]
        path = m.get("abs_path") or m.get("file")
        try:
            text = read_text_file(path)
            if not text:
                return ""
            lines = text.splitlines()
            start = max(0, int(m["start_line"]) - 1)
            end = min(len(lines), int(m["end_line"]))
            snippet = "\n".join(lines[start:end]).strip()
            if len(snippet) > max_chars:
                return snippet[:max_chars] + "\n..."
            return snippet
        except Exception:
            return ""

    def compose_answer(self, question: str, matches: List[Dict], max_sentences: int = 8, max_answer_chars: int = 1500) -> str:
        # Extractive summarization based on TF-IDF similarity of sentences to the question across top matches
        sentences = []
        sentence_meta = []
        for m in matches:
            snippet = m.get("snippet", "")
            if not snippet:
                continue
            # Split into sentences conservatively; also break long lines (code comments)
            parts = []
            for block in re.split(r"\n{2,}", snippet):
                parts.extend(SENTENCE_SPLIT_RE.split(block))
            for s in parts:
                s2 = s.strip()
                if len(s2) < 20:
                    continue
                sentences.append(s2)
                sentence_meta.append((m["file"], m["start_line"], m["end_line"]))
        if not sentences:
            # Fallback: concatenate snippets
            joined = []
            for m in matches:
                if m.get("snippet"):
                    joined.append(f"From {m['file']} L{m['start_line']}-{m['end_line']}:\n{m['snippet']}")
            return ("\n\n".join(joined))[:max_answer_chars]
        try:
            vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), norm="l2")
            X = vec.fit_transform(sentences + [question])
            q = X[-1, :]
            S = X[:-1, :]  # sentences
            sims = S.dot(q.T).toarray().ravel()
            idx = np.argsort(-sims)
        except Exception:
            idx = list(range(len(sentences)))
        chosen = []
        seen = set()
        for i in idx:
            s = sentences[i]
            # deduplicate by lowercased sentence
            key = s.lower()
            if key in seen:
                continue
            seen.add(key)
            chosen.append(s)
            if len(chosen) >= max_sentences:
                break
        # Preserve original order by their first appearance in the snippets
        ordered = [s for s in sentences if s in chosen]
        answer = "\n\n".join(ordered) if ordered else "\n\n".join(chosen)
        if len(answer) > max_answer_chars:
            answer = answer[:max_answer_chars] + "\n..."
        return answer

