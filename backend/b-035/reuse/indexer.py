import os
import re
import io
import ast
import hashlib
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel
import numpy as np

from .utils import default_config, iter_files, read_text_safely, chunk_lines


@dataclass
class Artifact:
    id: str
    path: str
    title: str
    kind: str
    start_line: int
    end_line: int
    content: str

    def to_dict(self, include_content: bool = False) -> Dict:
        d = {
            "id": self.id,
            "path": self.path,
            "title": self.title,
            "kind": self.kind,
            "start_line": self.start_line,
            "end_line": self.end_line,
        }
        if include_content:
            d["content"] = self.content
        return d


class CorpusIndex:
    def __init__(self, config: Dict):
        self.cfg = default_config()
        self.cfg.update(config or {})
        self.artifacts: List[Artifact] = []
        self._by_id: Dict[str, Artifact] = {}
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.matrix = None
        self.is_ready = False

    def build(self, force: bool = False):
        if self.is_ready and not force:
            return
        self.artifacts = self._scan_and_extract()
        self._by_id = {a.id: a for a in self.artifacts}
        texts = [self._normalize_text(a.content) for a in self.artifacts]
        self.vectorizer = TfidfVectorizer(
            max_features=self.cfg.get("max_features", 50000),
            ngram_range=tuple(self.cfg.get("ngram_range", [1, 2])),
            stop_words="english",
            lowercase=True,
        )
        if texts:
            self.matrix = self.vectorizer.fit_transform(texts)
        else:
            self.matrix = None
        self.is_ready = True

    def stats(self) -> Dict:
        return {
            "artifact_count": len(self.artifacts),
            "search_paths": self.cfg.get("search_paths", []),
            "include_extensions": self.cfg.get("include_extensions", []),
        }

    def get_artifact_by_id(self, artifact_id: str) -> Optional[Artifact]:
        return self._by_id.get(artifact_id)

    def query(self, text: str, top_k: int = 5) -> List[Tuple[Artifact, float]]:
        if not self.is_ready or self.matrix is None or self.vectorizer is None:
            return []
        q = self.vectorizer.transform([self._normalize_text(text)])
        sims = linear_kernel(q, self.matrix).ravel()
        if top_k <= 0:
            top_k = 5
        top_idx = np.argpartition(-sims, range(min(top_k, len(sims))))[:top_k]
        top_sorted = top_idx[np.argsort(-sims[top_idx])]
        results = []
        for idx in top_sorted:
            art = self.artifacts[int(idx)]
            score = float(sims[int(idx)])
            results.append((art, score))
        return results

    def _scan_and_extract(self) -> List[Artifact]:
        search_paths = self.cfg.get("search_paths", ["."])
        include_exts = set(self.cfg.get("include_extensions", [
            ".py", ".md", ".yml", ".yaml", ".json", ".txt"
        ]))
        ignore_dirs = set(self.cfg.get("ignore_dirs", [
            ".git", "node_modules", "venv", "__pycache__", ".tox", "dist", "build"
        ]))
        max_kb = int(self.cfg.get("max_file_size_kb", 512))
        artifacts: List[Artifact] = []
        for base in search_paths:
            for path in iter_files(base, include_exts, ignore_dirs):
                try:
                    st = os.stat(path)
                    if (st.st_size / 1024.0) > max_kb:
                        continue
                except Exception:
                    continue
                text = read_text_safely(path)
                if text is None:
                    continue
                kind = self._kind_for_path(path)
                extracted = self._extract_artifacts_from_file(path, text, kind)
                artifacts.extend(extracted)
        return artifacts

    def _kind_for_path(self, path: str) -> str:
        ext = os.path.splitext(path)[1].lower()
        if ext == ".py":
            return "python"
        if ext in (".md",):
            return "markdown"
        if ext in (".yaml", ".yml"):
            return "yaml"
        if ext in (".json",):
            return "json"
        return "text"

    def _extract_artifacts_from_file(self, path: str, text: str, kind: str) -> List[Artifact]:
        artifacts: List[Artifact] = []
        if kind == "python":
            artifacts.extend(self._extract_python(path, text))
        elif kind == "markdown":
            artifacts.extend(self._extract_markdown(path, text))
        else:
            artifacts.extend(self._extract_generic(path, text))
        return artifacts

    def _extract_python(self, path: str, text: str) -> List[Artifact]:
        artifacts: List[Artifact] = []
        try:
            tree = ast.parse(text)
        except Exception:
            return self._extract_generic(path, text)
        lines = text.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = getattr(node, 'name', 'object')
                start = getattr(node, 'lineno', 1)
                end = getattr(node, 'end_lineno', None)
                if end is None:
                    # fallback: span 50 lines max
                    end = min(start + 50, len(lines))
                segment = "\n".join(lines[start-1:end])
                title = f"{node.__class__.__name__.lower()} {name}"
                art_id = self._make_id(path, start, end, title)
                artifacts.append(Artifact(
                    id=art_id,
                    path=path,
                    title=title,
                    kind="python",
                    start_line=start,
                    end_line=end,
                    content=segment,
                ))
        # If nothing extracted, chunk file
        if not artifacts:
            artifacts.extend(self._extract_generic(path, text))
        return artifacts

    def _extract_markdown(self, path: str, text: str) -> List[Artifact]:
        artifacts: List[Artifact] = []
        lines = text.splitlines()
        # Find headings
        headings = []
        for idx, line in enumerate(lines, start=1):
            if re.match(r"^#{1,6}\\s+", line):
                headings.append((idx, line.lstrip('# ').strip()))
        if not headings:
            return self._extract_generic(path, text)
        bounds = []
        for i, (start, title) in enumerate(headings):
            end = len(lines) if i == len(headings) - 1 else headings[i+1][0] - 1
            bounds.append((start, end, title or f"section@{start}"))
        for start, end, title in bounds:
            segment = "\n".join(lines[start-1:end])
            art_id = self._make_id(path, start, end, title)
            artifacts.append(Artifact(
                id=art_id,
                path=path,
                title=title,
                kind="markdown",
                start_line=start,
                end_line=end,
                content=segment,
            ))
        return artifacts

    def _extract_generic(self, path: str, text: str) -> List[Artifact]:
        artifacts: List[Artifact] = []
        lines = text.splitlines()
        max_lines = int(self.cfg.get("chunk", {}).get("max_lines", 200))
        window = int(self.cfg.get("chunk", {}).get("window", 120))
        stride = int(self.cfg.get("chunk", {}).get("stride", 100))
        chunks = list(chunk_lines(lines, max_lines=max_lines, window=window, stride=stride))
        if not chunks:
            chunks = [(1, len(lines), lines)]
        for start, end, chunk in chunks:
            segment = "\n".join(chunk)
            title = f"{os.path.basename(path)}:{start}-{end}"
            art_id = self._make_id(path, start, end, title)
            artifacts.append(Artifact(
                id=art_id,
                path=path,
                title=title,
                kind=self._kind_for_path(path),
                start_line=start,
                end_line=end,
                content=segment,
            ))
        return artifacts

    def _normalize_text(self, s: str) -> str:
        return s

    def _make_id(self, path: str, start: int, end: int, title: str) -> str:
        h = hashlib.sha1()
        h.update(path.encode("utf-8", errors="ignore"))
        h.update(str(start).encode())
        h.update(str(end).encode())
        h.update(title.encode("utf-8", errors="ignore"))
        return h.hexdigest()[:16]

