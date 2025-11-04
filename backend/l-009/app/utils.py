import hashlib
import os
import tarfile
from pathlib import Path
from typing import Iterable
import fnmatch


def sha256_file(path: str, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def safe_extract_tar(tar: tarfile.TarFile, path: str):
    # Prevent path traversal
    def is_within_directory(directory: str, target: str) -> bool:
        abs_directory = os.path.abspath(directory)
        abs_target = os.path.abspath(target)
        return os.path.commonprefix([abs_directory, abs_target]) == abs_directory

    for member in tar.getmembers():
        member_path = os.path.join(path, member.name)
        if not is_within_directory(path, member_path):
            raise Exception("Attempted Path Traversal in Tar File")
    tar.extractall(path)


def iter_sources(sources: Iterable[str]) -> list[Path]:
    paths: list[Path] = []
    for s in sources:
        p = Path(s).expanduser().resolve()
        if p.exists():
            paths.append(p)
    return paths


def tar_add_with_excludes(tar: tarfile.TarFile, path: Path, arc_prefix: str, exclude_patterns: list[str] | None = None):
    exclude_patterns = exclude_patterns or []
    if path.is_file():
        if not any(fnmatch.fnmatch(path.name, pat) for pat in exclude_patterns):
            tar.add(str(path), arcname=os.path.join(arc_prefix, path.name), recursive=False)
        return

    for root, dirs, files in os.walk(path):
        # Exclude directories matching patterns
        dirs[:] = [d for d in dirs if not any(fnmatch.fnmatch(d, pat) for pat in exclude_patterns)]
        for f in files:
            if any(fnmatch.fnmatch(f, pat) for pat in exclude_patterns):
                continue
            full = Path(root) / f
            rel = os.path.relpath(full, start=path)
            tar.add(str(full), arcname=os.path.join(arc_prefix, rel))

