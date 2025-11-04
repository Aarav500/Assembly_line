import os
import shutil
import json
from typing import Optional, List, Dict


class LocalStorage:
    def __init__(self, base_path: str):
        self.base_path = os.path.abspath(base_path)
        self.archives_dir = os.path.join(self.base_path, "archives")
        self.metadata_dir = os.path.join(self.base_path, "metadata")
        self.drills_dir = os.path.join(self.base_path, "drills")
        os.makedirs(self.archives_dir, exist_ok=True)
        os.makedirs(self.metadata_dir, exist_ok=True)
        os.makedirs(self.drills_dir, exist_ok=True)

    def archive_path(self, backup_id: str) -> str:
        return os.path.join(self.archives_dir, f"{backup_id}.tar.gz")

    def metadata_path(self, backup_id: str) -> str:
        return os.path.join(self.metadata_dir, f"{backup_id}.json")

    def save_backup(self, tmp_archive_path: str, metadata: Dict) -> Dict:
        backup_id = metadata["id"]
        dest_archive = self.archive_path(backup_id)
        dest_meta = self.metadata_path(backup_id)
        os.makedirs(os.path.dirname(dest_archive), exist_ok=True)
        os.makedirs(os.path.dirname(dest_meta), exist_ok=True)
        shutil.move(tmp_archive_path, dest_archive)
        with open(dest_meta, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        return metadata

    def write_metadata(self, metadata: Dict):
        dest_meta = self.metadata_path(metadata["id"])
        with open(dest_meta, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

    def get_metadata(self, backup_id: str) -> Optional[Dict]:
        path = self.metadata_path(backup_id)
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def list_backups(self) -> List[Dict]:
        items: List[Dict] = []
        for name in os.listdir(self.metadata_dir):
            if not name.endswith(".json"):
                continue
            path = os.path.join(self.metadata_dir, name)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    items.append(meta)
            except Exception:
                continue
        return items

    def delete_backup(self, backup_id: str):
        archive = self.archive_path(backup_id)
        meta = self.metadata_path(backup_id)
        removed_any = False
        if os.path.isfile(archive):
            os.remove(archive)
            removed_any = True
        if os.path.isfile(meta):
            os.remove(meta)
            removed_any = True
        if not removed_any:
            raise FileNotFoundError(f"Backup {backup_id} not found")

    def record_drill_result(self, result: Dict):
        fname = os.path.join(self.drills_dir, f"drill_{result.get('timestamp','unknown')}.json")
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

