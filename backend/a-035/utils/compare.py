import hashlib
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import difflib


TextStat = Tuple[int, int]  # (added, removed)


def safe_relpath(relpath: str) -> str:
    # Normalize and prevent absolute or traversal
    p = Path(relpath)
    if p.is_absolute():
        p = Path(*p.parts[1:])
    new_parts = []
    for part in p.parts:
        if part in ("", "."):
            continue
        if part == "..":
            if new_parts:
                new_parts.pop()
            continue
        new_parts.append(part)
    return str(Path(*new_parts))


def list_files(root: Path) -> Dict[str, Path]:
    mapping: Dict[str, Path] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip version control dirs
        dirnames[:] = [d for d in dirnames if d not in {".git", ".hg", ".svn", "node_modules", "__pycache__"}]
        for fname in filenames:
            full = Path(dirpath) / fname
            try:
                rel = str(full.relative_to(root))
            except Exception:
                continue
            mapping[rel.replace("\\", "/")] = full
    return mapping


def md5sum(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(chunk_size), b''):
            h.update(chunk)
    return h.hexdigest()


def is_text_bytes(b: bytes) -> bool:
    if not b:
        return True
    # NUL byte implies binary
    if b"\x00" in b:
        return False
    # Heuristic: proportion of printable/whitespace
    text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x7F)) | set(range(0x80, 0x100)))
    nontext = b.translate(None, text_chars) if hasattr(b, 'translate') else b
    if hasattr(b, 'translate'):
        # In CPython, bytes.translate(None, delete) deletes those bytes
        pass
    # Fallback heuristic: try decode
    try:
        b.decode('utf-8')
        return True
    except Exception:
        # If most bytes are printable ascii
        pr = sum(1 for x in b if 32 <= x <= 126 or x in (9, 10, 13)) / max(1, len(b))
        return pr > 0.85


def is_text_file(path: Path) -> bool:
    try:
        with open(path, 'rb') as f:
            head = f.read(4000)
            return is_text_bytes(head)
    except Exception:
        return False


def read_text_lines(path: Path) -> List[str]:
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read().splitlines()


def diff_stats(lines_a: List[str], lines_b: List[str]) -> TextStat:
    added = 0
    removed = 0
    for line in difflib.ndiff(lines_a, lines_b):
        if line.startswith('+ '):
            added += 1
        elif line.startswith('- '):
            removed += 1
    return added, removed


def compare_projects(dir_a: Path, dir_b: Path, label_a: str = "A", label_b: str = "B") -> dict:
    dir_a = Path(dir_a)
    dir_b = Path(dir_b)

    files_a = list_files(dir_a)
    files_b = list_files(dir_b)

    all_paths = sorted(set(files_a.keys()) | set(files_b.keys()))

    result_files = []
    summary = {
        "files_a": len(files_a),
        "files_b": len(files_b),
        "added": 0,
        "removed": 0,
        "modified": 0,
        "unchanged": 0,
        "binary": 0,
    }

    for rel in all_paths:
        a_path = files_a.get(rel)
        b_path = files_b.get(rel)
        entry = {
            "path": rel,
            "status": None,
            "is_text": None,
            "size_a": None,
            "size_b": None,
            "hash_a": None,
            "hash_b": None,
            "lines_added": None,
            "lines_removed": None,
        }
        if a_path and not b_path:
            entry.update({
                "status": "removed",
                "is_text": is_text_file(a_path),
                "size_a": a_path.stat().st_size if a_path.exists() else None,
            })
            summary["removed"] += 1
        elif b_path and not a_path:
            entry.update({
                "status": "added",
                "is_text": is_text_file(b_path),
                "size_b": b_path.stat().st_size if b_path.exists() else None,
            })
            summary["added"] += 1
        else:
            # both exist
            size_a = a_path.stat().st_size if a_path.exists() else None
            size_b = b_path.stat().st_size if b_path.exists() else None
            hash_a = md5sum(a_path) if a_path.exists() else None
            hash_b = md5sum(b_path) if b_path.exists() else None

            if hash_a == hash_b:
                entry.update({
                    "status": "unchanged",
                    "is_text": is_text_file(a_path),
                    "size_a": size_a,
                    "size_b": size_b,
                    "hash_a": hash_a,
                    "hash_b": hash_b,
                })
                summary["unchanged"] += 1
            else:
                text_a = is_text_file(a_path)
                text_b = is_text_file(b_path)
                entry.update({
                    "size_a": size_a,
                    "size_b": size_b,
                    "hash_a": hash_a,
                    "hash_b": hash_b,
                })
                if text_a and text_b:
                    la = read_text_lines(a_path)
                    lb = read_text_lines(b_path)
                    a_add, a_rem = diff_stats(la, lb)
                    entry.update({
                        "status": "modified",
                        "is_text": True,
                        "lines_added": a_add,
                        "lines_removed": a_rem,
                    })
                    summary["modified"] += 1
                else:
                    entry.update({
                        "status": "modified",
                        "is_text": False,
                    })
                    summary["binary"] += 1

        result_files.append(entry)

    return {
        "labels": {"a": label_a, "b": label_b},
        "summary": summary,
        "files": result_files,
        "roots": {"a": str(dir_a), "b": str(dir_b)},
    }


def generate_html_diff(path_a: Optional[Path], path_b: Optional[Path], label_a: str = "A", label_b: str = "B") -> str:
    html_diff = difflib.HtmlDiff(wrapcolumn=120)
    if path_a is not None and path_b is not None:
        a_lines = read_text_lines(path_a)
        b_lines = read_text_lines(path_b)
    elif path_a is not None:
        a_lines = read_text_lines(path_a)
        b_lines = []
    else:
        a_lines = []
        b_lines = read_text_lines(path_b) if path_b is not None else []

    table = html_diff.make_table(a_lines, b_lines, fromdesc=label_a, todesc=label_b, context=True, numlines=3)
    # Wrap in minimal container
    return f"""
    <div class=\"diff-container\">{table}</div>
    """

