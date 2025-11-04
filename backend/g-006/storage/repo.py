import os
import json
from typing import Dict, List, Optional


class FileRepo:
    def __init__(self, base_dir: str = "data"):
        self.base_dir = base_dir
        self.models_dir = os.path.join(self.base_dir, "models")
        os.makedirs(self.models_dir, exist_ok=True)

    def _model_dir(self, model_id: str) -> str:
        return os.path.join(self.models_dir, model_id)

    def save_model_record(self, record: dict, files: Dict[str, str]) -> Dict[str, str]:
        model_id = record["id"]
        mdir = self._model_dir(model_id)
        os.makedirs(mdir, exist_ok=True)
        # Persist main record as model.json (also in files)
        for fname, content in files.items():
            path = os.path.join(mdir, fname)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        # Index file for quick list
        index_path = os.path.join(mdir, "index.json")
        index_data = {
            "id": record.get("id"),
            "name": record.get("name"),
            "version": record.get("version"),
            "owner": record.get("owner", {}),
            "updated_at": record.get("updated_at"),
            "created_at": record.get("created_at"),
            "description": record.get("description", "")[:300]
        }
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index_data, f, indent=2, ensure_ascii=False)
        return {k: os.path.join(mdir, k) for k in files.keys()}

    def load_model(self, model_id: str) -> Optional[dict]:
        mdir = self._model_dir(model_id)
        path = os.path.join(mdir, "model.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_models(self) -> List[dict]:
        items = []
        if not os.path.exists(self.models_dir):
            return items
        for entry in os.listdir(self.models_dir):
            mdir = os.path.join(self.models_dir, entry)
            if not os.path.isdir(mdir):
                continue
            idx = os.path.join(mdir, "index.json")
            if os.path.exists(idx):
                try:
                    with open(idx, "r", encoding="utf-8") as f:
                        items.append(json.load(f))
                except Exception:
                    # Continue on parse errors
                    pass
        # Sort by updated_at desc
        items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        return items

    def get_artifact_paths(self, model_id: str) -> dict:
        mdir = self._model_dir(model_id)
        artifacts = {}
        for name in ["model.json", "model_card.md", "compliance.json"]:
            path = os.path.join(mdir, name)
            if os.path.exists(path):
                artifacts[name] = path
        return artifacts

    def get_file_path(self, model_id: str, filename: str) -> Optional[str]:
        path = os.path.join(self._model_dir(model_id), filename)
        if os.path.exists(path):
            return path
        return None

    def write_artifacts(self, model_id: str, files: Dict[str, str]):
        mdir = self._model_dir(model_id)
        os.makedirs(mdir, exist_ok=True)
        for fname, content in files.items():
            with open(os.path.join(mdir, fname), "w", encoding="utf-8") as f:
                f.write(content)
        # update index updated_at if model.json updated
        model_path = os.path.join(mdir, "model.json")
        if os.path.exists(model_path):
            try:
                with open(model_path, "r", encoding="utf-8") as f:
                    rec = json.load(f)
                idx = {
                    "id": rec.get("id"),
                    "name": rec.get("name"),
                    "version": rec.get("version"),
                    "owner": rec.get("owner", {}),
                    "updated_at": rec.get("updated_at"),
                    "created_at": rec.get("created_at"),
                    "description": rec.get("description", "")[:300]
                }
                with open(os.path.join(mdir, "index.json"), "w", encoding="utf-8") as outf:
                    json.dump(idx, outf, indent=2, ensure_ascii=False)
            except Exception:
                pass

