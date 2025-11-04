import os
import fnmatch
import json
from typing import Dict, List, Optional, Iterable
from .models import Document
from config import MAX_FILE_SIZE_BYTES, MAX_DOC_LENGTH

CODE_EXTS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rb", ".rs", ".c", ".h", ".cpp", ".hpp", ".cs", ".php", ".scala", ".swift",
}
DOC_EXTS = {".md", ".rst", ".txt"}
DATA_EXTS = {".json", ".yaml", ".yml"}
NB_EXT = ".ipynb"


def detect_type(path: str) -> str:
    p = path.lower()
    if "/ideas/" in p or p.endswith(".idea"):
        return "idea"
    if "/models/" in p or os.path.basename(p) in {"model.yaml", "model.yml", "model.json"}:
        return "model"
    ext = os.path.splitext(p)[1]
    if ext in CODE_EXTS:
        return "code"
    if ext in DOC_EXTS:
        return "doc"
    if ext in DATA_EXTS:
        return "doc"
    if ext == NB_EXT:
        return "doc"
    return "other"


def read_text_file(path: str) -> Optional[str]:
    try:
        if os.path.getsize(path) > MAX_FILE_SIZE_BYTES:
            return None
    except OSError:
        return None
    try:
        if path.lower().endswith(NB_EXT):
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                nb = json.load(f)
            cells = []
            for c in nb.get("cells", []):
                src = c.get("source")
                if isinstance(src, list):
                    cells.append("".join(src))
                elif isinstance(src, str):
                    cells.append(src)
            return "\n\n".join(cells)[: MAX_DOC_LENGTH]
        else:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()[: MAX_DOC_LENGTH]
    except Exception:
        return None


def iter_files(roots: Iterable[str]) -> Iterable[str]:
    for root in roots:
        if not root:
            continue
        if os.path.isfile(root):
            yield root
        else:
            for dirpath, _, filenames in os.walk(root):
                for fn in filenames:
                    yield os.path.join(dirpath, fn)


def scan_paths(
    roots: List[str],
    include_globs: Optional[List[str]] = None,
    exclude_globs: Optional[List[str]] = None,
) -> List[Dict]:
    include_globs = include_globs or ["**/*"]
    exclude_globs = exclude_globs or ["**/.git/**", "**/node_modules/**", "**/.venv/**", "**/__pycache__/**"]

    matched = []
    for path in iter_files(roots):
        rel = path
        inc_ok = any(fnmatch.fnmatch(rel, pat) for pat in include_globs)
        exc_hit = any(fnmatch.fnmatch(rel, pat) for pat in exclude_globs)
        if not inc_ok or exc_hit:
            continue
        content = read_text_file(path)
        if not content:
            continue
        stype = detect_type(path)
        title = os.path.basename(path)
        matched.append({
            "path": path,
            "title": title,
            "content": content,
            "source_type": stype,
            "tags": [],
            "extra": {},
        })
    return matched

