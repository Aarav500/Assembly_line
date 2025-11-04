import os
import shutil
from typing import Tuple

class Storage:
    def __init__(self, base_dir: str):
        self.base_dir = os.path.abspath(base_dir)
        self.artifacts_dir = os.path.join(self.base_dir, "artifacts")
        self.modules_dir = os.path.join(self.base_dir, "modules")
        os.makedirs(self.artifacts_dir, exist_ok=True)
        os.makedirs(self.modules_dir, exist_ok=True)

    def artifact_blob_path(self, name: str, hash_hex: str) -> str:
        d = os.path.join(self.artifacts_dir, name)
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, f"{hash_hex}")

    def module_blob_path(self, name: str, version: str, filename: str) -> str:
        d = os.path.join(self.modules_dir, name, version)
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, filename)

    def install_tempfile(self, tmp_path: str, final_path: str):
        final_dir = os.path.dirname(final_path)
        os.makedirs(final_dir, exist_ok=True)
        # use atomic move when possible
        os.replace(tmp_path, final_path)

