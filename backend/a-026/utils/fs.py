import os
from typing import Generator, Tuple, Iterable, Set


def iter_code_files(root: str, exts: Iterable[str], ignore_dirs: Set[str]) -> Generator[Tuple[str, str], None, None]:
    root = os.path.abspath(root)
    for dirpath, dirnames, filenames in os.walk(root):
        # mutate dirnames to skip ignored
        dirnames[:] = [d for d in dirnames if d not in ignore_dirs and not d.startswith('.')]
        for fn in filenames:
            if fn.startswith('.'):
                continue
            ext = os.path.splitext(fn)[1].lower()
            if ext in exts:
                abs_path = os.path.join(dirpath, fn)
                rel_path = os.path.relpath(abs_path, root)
                yield abs_path, rel_path


def read_text_file(path: str) -> str:
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()


def find_requirements(root: str) -> str:
    candidates = [
        os.path.join(root, 'requirements.txt'),
        os.path.join(root, 'reqs.txt'),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return ''

