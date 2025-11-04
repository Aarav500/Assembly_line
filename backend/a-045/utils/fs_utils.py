import os
from typing import Iterator, Optional


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def iter_relative_files(base_dir: str) -> Iterator[str]:
    if not os.path.isdir(base_dir):
        return iter(())
    for root, _, files in os.walk(base_dir):
        for f in files:
            abs_path = os.path.join(root, f)
            rel = os.path.relpath(abs_path, start=base_dir)
            yield rel.replace('\\', '/')


def safe_join(base: str, *paths: str) -> Optional[str]:
    # Similar to Flask's safe_join: build a path and ensure it is within base
    final_path = os.path.abspath(os.path.join(base, *paths))
    base_abs = os.path.abspath(base)
    if os.path.commonpath([final_path, base_abs]) != base_abs:
        return None
    return final_path


def is_subpath(path: str, base: str) -> bool:
    try:
        return os.path.commonpath([os.path.abspath(path), os.path.abspath(base)]) == os.path.abspath(base)
    except ValueError:
        return False

