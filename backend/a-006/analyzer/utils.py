import os
from collections import defaultdict

DEFAULT_EXCLUDE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    "__pycache__",
    "node_modules",
    "venv",
    ".venv",
    "dist",
    "build",
    "target",
    ".mypy_cache",
    ".pytest_cache",
}

INCLUDE_EXTS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rb", ".php", ".c", ".h", ".cpp", ".cc", ".cs", ".sh"
}

LANG_BY_EXT = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".jsx": "JavaScript",
    ".java": "Java",
    ".go": "Go",
    ".rb": "Ruby",
    ".php": "PHP",
    ".c": "C",
    ".h": "C/C++ Header",
    ".cpp": "C++",
    ".cc": "C++",
    ".cs": "C#",
    ".sh": "Shell",
}

def is_excluded_dir(name: str) -> bool:
    return name in DEFAULT_EXCLUDE_DIRS or name.startswith(".") and name not in {".", ".."}

def iter_source_files(base_path: str):
    base_path = os.path.abspath(base_path)
    for root, dirs, files in os.walk(base_path):
        # prune excluded dirs
        dirs[:] = [d for d in dirs if not is_excluded_dir(d)]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in INCLUDE_EXTS:
                full = os.path.join(root, f)
                yield full


def count_lines(content: str):
    lines = content.splitlines()
    total = len(lines)
    non_empty = sum(1 for l in lines if l.strip())
    return total, non_empty


def read_text(path: str):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def ext_language(ext: str) -> str:
    return LANG_BY_EXT.get(ext.lower(), ext.lower().lstrip("."))


def rel_module_name(base_path: str, file_path: str) -> str:
    # Infer Python-like module path from file path
    rel = os.path.relpath(file_path, base_path)
    rel = rel.replace(os.sep, "/")
    if rel.endswith(".py"):
        rel = rel[:-3]
    parts = []
    for p in rel.split("/"):
        if p == "__init__":
            continue
        parts.append(p)
    return ".".join(parts)


def build_internal_module_index(base_path: str):
    # Map module names to file paths (Python only)
    index = {}
    for f in iter_source_files(base_path):
        if f.endswith(".py"):
            mod = rel_module_name(base_path, f)
            index[mod] = f
    return index


def aggregate_by_ext(file_infos):
    by_ext = defaultdict(lambda: {"files": 0, "lines": 0})
    for fi in file_infos:
        ext = fi["extension"]
        by_ext[ext]["files"] += 1
        by_ext[ext]["lines"] += fi["lines"]
    results = []
    for ext, data in sorted(by_ext.items(), key=lambda kv: kv[1]["lines"], reverse=True):
        results.append({
            "extension": ext,
            "language": ext_language(ext),
            "files": data["files"],
            "lines": data["lines"],
        })
    return results

