import os
import json
import shutil
import time
import uuid
import errno
from pathlib import Path
from typing import Optional, Dict, List
from utils.lock import FileLock
import config


def _safe_rmtree(path: Path):
    def onerror(func, p, exc_info):
        import stat
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except Exception:
            pass
    if path.exists():
        shutil.rmtree(path, onerror=onerror)


def _dir_size(path: Path) -> int:
    size = 0
    for root, dirs, files in os.walk(path):
        for f in files:
            try:
                size += (Path(root) / f).stat().st_size
            except FileNotFoundError:
                pass
    return size


class SnapshotManager:
    def __init__(self, base_dir: str, workspace_dir: str, snapshot_dir: str):
        self.base_dir = Path(base_dir).resolve()
        self.workspace_dir = (self.base_dir / workspace_dir).resolve()
        self.snapshots_dir = (self.base_dir / snapshot_dir).resolve()
        self.lock_path = self.snapshots_dir / ".snapshots.lock"
        self.index_path = self.snapshots_dir / "index.json"

        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            self._write_index({"snapshots": []})

    def _read_index(self) -> Dict:
        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"snapshots": []}

    def _write_index(self, data: Dict):
        tmp = self.index_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, self.index_path)

    def _slugify(self, text: str) -> str:
        import re
        text = text.strip().lower()
        text = re.sub(r"[^a-z0-9]+", "-", text)
        return text.strip("-")

    def _gen_id(self, label: Optional[str] = None) -> str:
        ts = time.strftime("%Y%m%d-%H%M%S")
        suffix = uuid.uuid4().hex[:6]
        if label:
            return f"{ts}-{self._slugify(label)}-{suffix}"
        return f"{ts}-{suffix}"

    def list_snapshots(self) -> List[Dict]:
        data = self._read_index()
        snaps = data.get("snapshots", [])
        snaps.sort(key=lambda s: s.get("created_at", 0), reverse=True)
        return snaps

    def get_snapshot(self, snapshot_id: str) -> Optional[Dict]:
        data = self._read_index()
        for s in data.get("snapshots", []):
            if s.get("id") == snapshot_id:
                return s
        return None

    def create_snapshot(self, label: Optional[str] = None, metadata: Optional[Dict] = None) -> Dict:
        with FileLock(self.lock_path, timeout=60):
            snap_id = self._gen_id(label)
            dest = self.snapshots_dir / snap_id
            if dest.exists():
                raise FileExistsError(f"Snapshot path already exists: {dest}")
            # Copy workspace into snapshot dir (excluding __pycache__)
            def ignore(dir, entries):
                ignored = []
                if os.path.basename(dir) == "__pycache__":
                    ignored.extend(entries)
                return [e for e in entries if e == "__pycache__"]
            shutil.copytree(self.workspace_dir, dest, copy_function=shutil.copy2, dirs_exist_ok=False, ignore=shutil.ignore_patterns("__pycache__"))
            size = _dir_size(dest)
            created_at = int(time.time())
            entry = {
                "id": snap_id,
                "label": label,
                "created_at": created_at,
                "path": str(dest),
                "size_bytes": size,
                "metadata": metadata or {},
            }
            data = self._read_index()
            data.setdefault("snapshots", []).append(entry)
            self._write_index(data)
            return entry

    def rollback(self, snapshot_id: str) -> Dict:
        with FileLock(self.lock_path, timeout=60):
            snap = self.get_snapshot(snapshot_id)
            if not snap:
                raise FileNotFoundError(f"Snapshot not found: {snapshot_id}")
            snap_path = Path(snap["path"]).resolve()
            if not snap_path.exists():
                raise FileNotFoundError(f"Snapshot directory missing: {snap_path}")

            parent = self.workspace_dir.parent
            tmp_target = parent / f".{self.workspace_dir.name}.tmp-{uuid.uuid4().hex[:8]}"
            backup = parent / f".{self.workspace_dir.name}.bak-{uuid.uuid4().hex[:8]}"

            # Prepare tmp target with snapshot contents
            shutil.copytree(snap_path, tmp_target, copy_function=shutil.copy2)

            # Move current workspace to backup (if exists)
            if self.workspace_dir.exists():
                os.replace(self.workspace_dir, backup)
            else:
                backup = None

            try:
                os.replace(tmp_target, self.workspace_dir)
            except Exception as e:
                # restore backup if present
                if self.workspace_dir.exists():
                    _safe_rmtree(self.workspace_dir)
                if backup and backup.exists():
                    os.replace(backup, self.workspace_dir)
                raise e

            # cleanup backup
            if backup and backup.exists():
                _safe_rmtree(backup)

            return {
                "id": snap["id"],
                "label": snap.get("label"),
                "created_at": snap.get("created_at"),
                "path": str(snap_path),
                "size_bytes": snap.get("size_bytes"),
            }

    def delete_snapshot(self, snapshot_id: str) -> bool:
        with FileLock(self.lock_path, timeout=60):
            data = self._read_index()
            snaps = data.get("snapshots", [])
            idx = None
            for i, s in enumerate(snaps):
                if s.get("id") == snapshot_id:
                    idx = i
                    break
            if idx is None:
                return False
            snap = snaps.pop(idx)
            self._write_index(data)
            # remove snapshot directory
            snap_path = Path(snap.get("path", ""))
            if snap_path.exists():
                _safe_rmtree(snap_path)
            return True

