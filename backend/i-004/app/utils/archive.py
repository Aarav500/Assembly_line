import os
import tarfile
import zipfile
from typing import List, Optional, Set


def _is_archive(filename: str) -> bool:
    lower = filename.lower()
    return lower.endswith(".zip") or lower.endswith(".tar") or lower.endswith(".tar.gz") or lower.endswith(".tgz") or lower.endswith(".tar.bz2") or lower.endswith(".tbz2")


def _extract_archive(archive_path: str, dest_dir: str) -> str:
    os.makedirs(dest_dir, exist_ok=True)
    lower = archive_path.lower()
    if lower.endswith(".zip"):
        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(dest_dir)
    elif lower.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2")):
        with tarfile.open(archive_path, "r:*") as tf:
            tf.extractall(dest_dir)
    else:
        raise ValueError(f"Unsupported archive type: {archive_path}")
    return dest_dir


def save_uploads_to_temp(uploads: List, workdir: str) -> List[str]:
    roots: List[str] = []
    os.makedirs(workdir, exist_ok=True)
    for up in uploads:
        filename = up.filename or "upload"
        dest_path = os.path.join(workdir, filename)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        up.save(dest_path)
        if _is_archive(filename):
            extract_dir = os.path.join(workdir, f"extracted_{os.path.basename(filename)}")
            _extract_archive(dest_path, extract_dir)
            roots.append(extract_dir)
        else:
            roots.append(dest_path)
    return roots


def collect_candidate_files(root: str, include_extensions: Optional[Set[str]] = None) -> List[str]:
    candidates: List[str] = []

    if os.path.isfile(root):
        ext = os.path.splitext(root)[1].lstrip(".")
        if include_extensions is None or ext in include_extensions:
            candidates.append(root)
        return candidates

    for base, _, files in os.walk(root):
        for f in files:
            path = os.path.join(base, f)
            ext = os.path.splitext(f)[1].lstrip(".")
            # Support files without ext like Dockerfile if not filtered strictly
            if include_extensions is None:
                candidates.append(path)
            else:
                if ext in include_extensions:
                    candidates.append(path)
    return candidates

