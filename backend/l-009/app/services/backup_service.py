import os
import tarfile
from datetime import datetime, timezone
import tempfile
import uuid
from typing import List, Optional, Dict
from ..utils import sha256_file, iter_sources, tar_add_with_excludes


class BackupService:
    def __init__(self, storage, backup_cfg: dict):
        self.storage = storage
        self.backup_cfg = backup_cfg or {}

    def _new_backup_id(self) -> str:
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        u = uuid.uuid4().hex[:8]
        return f"{ts}_{u}"

    def create_backup(self, reason: str = "manual", sources: Optional[List[str]] = None) -> Dict:
        sources = sources or self.backup_cfg.get("sources", [])
        exclude_patterns = self.backup_cfg.get("exclude_patterns", [])
        resolved_sources = iter_sources(sources)
        if not resolved_sources:
            raise ValueError("No valid sources to backup")

        backup_id = self._new_backup_id()
        tmp_dir = tempfile.mkdtemp(prefix="backup_tmp_")
        tmp_archive = os.path.join(tmp_dir, f"{backup_id}.tar.gz")

        meta = {
            "id": backup_id,
            "timestamp": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
            "archive_filename": f"{backup_id}.tar.gz",
            "size_bytes": 0,
            "checksum_sha256": None,
            "sources": [str(p) for p in resolved_sources],
            "reason": reason,
            "status": "pending",
            "error": None,
        }

        try:
            with tarfile.open(tmp_archive, mode="w:gz") as tar:
                for src in resolved_sources:
                    arc_prefix = os.path.basename(str(src)) or "root"
                    tar_add_with_excludes(tar, src, arc_prefix=arc_prefix, exclude_patterns=exclude_patterns)

            size = os.path.getsize(tmp_archive)
            checksum = sha256_file(tmp_archive)
            meta["size_bytes"] = size
            meta["checksum_sha256"] = checksum
            meta["status"] = "success"
            saved = self.storage.save_backup(tmp_archive, meta)
            return saved
        except Exception as e:
            meta["status"] = "failed"
            meta["error"] = str(e)
            try:
                self.storage.write_metadata(meta)
            except Exception:
                pass
            raise
        finally:
            try:
                if os.path.isfile(tmp_archive):
                    os.remove(tmp_archive)
            except Exception:
                pass
            try:
                if os.path.isdir(tmp_dir):
                    os.rmdir(tmp_dir)
            except Exception:
                pass

