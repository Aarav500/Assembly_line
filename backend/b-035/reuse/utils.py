import os
import yaml
from typing import Dict, Iterable, List, Tuple, Optional


def default_config() -> Dict:
    return {
        "search_paths": ["."],
        "include_extensions": [".py", ".md", ".yml", ".yaml", ".json", ".txt"],
        "ignore_dirs": [
            ".git", "node_modules", "venv", "__pycache__", ".tox", "dist", "build"
        ],
        "max_file_size_kb": 512,
        "chunk": {"max_lines": 200, "window": 120, "stride": 100},
        "max_features": 50000,
        "ngram_range": [1, 2],
    }


def load_config(path: str) -> Dict:
    base = default_config()
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
                base.update(cfg)
    except Exception:
        pass
    return base


def iter_files(base_path: str, include_exts, ignore_dirs) -> Iterable[str]:
    include_exts = set(include_exts)
    ignore_dirs = set(ignore_dirs)

    for root, dirs, files in os.walk(base_path):
        # prune ignored dirs
        dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('.')]
        for fn in files:
            ext = os.path.splitext(fn)[1].lower()
            if ext in include_exts:
                yield os.path.join(root, fn)


def read_text_safely(path: str) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        try:
            with open(path, "r", encoding="latin-1") as f:
                return f.read()
        except Exception:
            return None
    except Exception:
        return None


def chunk_lines(lines: List[str], max_lines: int = 200, window: int = 120, stride: int = 100) -> Iterable[Tuple[int, int, List[str]]]:
    n = len(lines)
    if n == 0:
        return []
    if n <= max_lines:
        yield (1, n, lines)
        return
    i = 0
    # 1-based line numbers
    while i < n:
        start = i + 1
        end = min(i + window, n)
        yield (start, end, lines[i:end])
        if end == n:
            break
        i += stride

