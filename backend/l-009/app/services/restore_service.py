import os
import tarfile
from typing import Dict
from ..utils import safe_extract_tar, sha256_file


class RestoreService:
    def __init__(self, storage):
        self.storage = storage

    def restore_backup(self, backup_id: str, target_path: str, verify_checksum: bool = True) -> Dict:
        meta = self.storage.get_metadata(backup_id)
        if not meta:
            raise FileNotFoundError(f"Metadata for {backup_id} not found")
        archive_path = self.storage.archive_path(backup_id)
        if not os.path.isfile(archive_path):
            raise FileNotFoundError(f"Archive for {backup_id} not found")

        if verify_checksum:
            ch = sha256_file(archive_path)
            if meta.get("checksum_sha256") and ch != meta.get("checksum_sha256"):
                raise ValueError("Checksum verification failed")

        os.makedirs(target_path, exist_ok=True)
        with tarfile.open(archive_path, mode="r:gz") as tar:
            safe_extract_tar(tar, target_path)
        return {
            "status": "success",
            "restored_to": os.path.abspath(target_path),
            "backup_id": backup_id,
            "files_restored_from": os.path.basename(archive_path),
        }

