import os
import json
from typing import Optional


class Storage:
    def __init__(self, redacted_dir: str):
        self.redacted_dir = redacted_dir
        os.makedirs(self.redacted_dir, exist_ok=True)

    def _paths(self, file_id: str):
        base = os.path.join(self.redacted_dir, file_id)
        txt = base + '.txt'
        meta = base + '.json'
        return txt, meta

    def save(self, file_id: str, redacted_text: str, metadata: dict):
        txt_path, meta_path = self._paths(file_id)
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(redacted_text)
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    def load_redacted(self, file_id: str) -> Optional[str]:
        txt_path, _ = self._paths(file_id)
        if not os.path.exists(txt_path):
            return None
        with open(txt_path, 'r', encoding='utf-8') as f:
            return f.read()

    def load_metadata(self, file_id: str) -> Optional[dict]:
        _, meta_path = self._paths(file_id)
        if not os.path.exists(meta_path):
            return None
        with open(meta_path, 'r', encoding='utf-8') as f:
            return json.load(f)

