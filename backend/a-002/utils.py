import os
import shutil
import stat
import zipfile
from pathlib import Path
from typing import Iterable, Dict, Any
import sys

from config import ALLOWED_BASE_DIRS


def ensure_dir(path: Path) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def sanitize_project_name(name: str) -> str:
    # Keep alnum, dash, underscore, dot; replace others with hyphen
    if not name:
        return ""
    allowed = []
    for ch in name.strip():
        if ch.isalnum() or ch in ("-", "_", "."):
            allowed.append(ch)
        else:
            allowed.append("-")
    result = "".join(allowed).strip("-._")
    return result[:128]


def unique_project_path(base_dir: Path | str, name: str) -> Path:
    base = Path(base_dir)
    candidate = base / name
    counter = 1
    while candidate.exists():
        candidate = base / f"{name}-{counter}"
        counter += 1
    return candidate


def safe_extract_zip(zip_path: Path | str, dest_dir: Path | str) -> None:
    dest = Path(dest_dir)
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            # Prevent zip slip
            member_name = member.filename
            if member_name.startswith("/") or member_name.startswith("\\"):
                raise ValueError(f"Illegal absolute path in archive: {member_name}")
            # Normalize path
            resolved = (dest / member_name).resolve()
            if not str(resolved).startswith(str(dest.resolve())):
                raise ValueError(f"Illegal path in archive: {member_name}")
        zf.extractall(dest)


def _normalize_path(p: Path) -> Path:
    try:
        return p.resolve(strict=False)
    except Exception:
        # On some filesystems/permissions, resolve may fail; fallback to absolute
        return p.absolute()


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except Exception:
        return False


def is_source_dir_allowed(source_dir: Path) -> bool:
    src = _normalize_path(source_dir)
    # If an allowed entry is a UNC prefix (\\\\), allow UNC paths
    if src.drive.startswith("\\\\"):
        # If any allowed base equals \\\\ or starts with \\\\, allow
        for b in ALLOWED_BASE_DIRS:
            if b.startswith("\\\\"):
                # If b is exactly \\\\ treat as allow all UNC; otherwise check prefix
                if b == "\\\\":
                    return True
                # Compare case-insensitive on Windows
                if str(src).lower().startswith(str(Path(b)).lower()):
                    return True
        return False

    for base in ALLOWED_BASE_DIRS:
        try:
            bpath = _normalize_path(Path(base))
        except Exception:
            continue
        # Must exist and be a directory to be considered
        if not bpath.exists():
            # If base is a root-like path (e.g., /mnt), still allow even if not present
            pass
        if _is_relative_to(src, bpath):
            return True
        # Also allow if src equals base
        if str(src).rstrip(os.sep) == str(bpath).rstrip(os.sep):
            return True
    return False


def link_or_copy_project(source_dir: Path | str, dest_dir: Path | str, prefer_symlink: bool = True) -> Dict[str, Any]:
    src = Path(source_dir)
    dest = Path(dest_dir)
    if dest.exists():
        raise FileExistsError(f"Destination already exists: {dest}")

    # Try to create a directory that represents the project root.
    # If symlinking the whole directory, we can symlink dest to src.
    if prefer_symlink:
        try:
            # On Windows, directory symlink may require privileges; try junction as fallback
            if os.name == "nt":
                try:
                    os.symlink(str(src), str(dest), target_is_directory=True)
                    return {"linked": True, "method": "symlink"}
                except (OSError, NotImplementedError):
                    # Create directory junction using mklink /J via os.system is not ideal; use WinAPI via os.replace trick is non-trivial
                    # Fallback to copying if symlink fails
                    pass
            else:
                os.symlink(src, dest, target_is_directory=True)
                return {"linked": True, "method": "symlink"}
        except Exception:
            # Fallback to copy
            pass

    # Copy directory contents
    shutil.copytree(src, dest, symlinks=False, dirs_exist_ok=False)
    return {"linked": False, "method": "copy"}


def get_project_metadata(project_path: Path | str) -> Dict[str, Any]:
    p = Path(project_path)
    meta: Dict[str, Any] = {"files": 0, "size_bytes": 0, "link": False}
    try:
        # Check if project root is a symlink
        if p.is_symlink():
            meta["link"] = True
        for root, dirs, files in os.walk(p):
            for f in files:
                meta["files"] += 1
                fp = Path(root) / f
                try:
                    meta["size_bytes"] += fp.stat().st_size
                except Exception:
                    pass
    except Exception:
        pass
    return meta

