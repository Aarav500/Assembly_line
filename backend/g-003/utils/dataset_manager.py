import os
import io
import json
import shutil
import hashlib
from datetime import datetime
from typing import List, Tuple, Optional, Dict
import zipfile


class DatasetManager:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def dataset_exists(self, name: str) -> bool:
        return os.path.isdir(self._dataset_dir(name))

    def list_datasets(self) -> Dict:
        out = {}
        for name in sorted(os.listdir(self.base_dir)):
            ddir = self._dataset_dir(name)
            if os.path.isdir(ddir):
                meta = self._read_meta(name)
                out[name] = meta if meta else {"name": name, "versions": []}
        return out

    def get_dataset_info(self, name: str) -> Optional[Dict]:
        if not self.dataset_exists(name):
            return None
        meta = self._read_meta(name)
        if not meta:
            return {"name": name, "versions": []}
        return meta

    def get_latest_version(self, name: str) -> Optional[str]:
        info = self.get_dataset_info(name)
        if not info or not info.get('versions'):
            return None
        return info['versions'][-1]['version']

    def get_dataset_version_info(self, name: str, version: str) -> Optional[Dict]:
        info = self.get_dataset_info(name)
        if not info:
            return None
        for v in info.get('versions', []):
            if v['version'] == version:
                return v
        return None

    def get_version_path(self, name: str, version: str) -> Optional[str]:
        vdir = os.path.join(self._dataset_dir(name), version)
        return vdir if os.path.isdir(vdir) else None

    def create_dataset_version(self, name: str, files: List[Tuple[str, bytes]], metadata: Dict) -> Dict:
        os.makedirs(self._dataset_dir(name), exist_ok=True)
        info = self._read_meta(name) or {"name": name, "versions": []}
        next_version = self._next_version_id(info)
        vdir = os.path.join(self._dataset_dir(name), next_version)
        os.makedirs(vdir, exist_ok=True)

        saved = []
        for filename, data in files:
            path = os.path.join(vdir, filename)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'wb') as f:
                f.write(data)
            saved.append(filename)
            if zipfile.is_zipfile(io.BytesIO(data)):
                try:
                    with zipfile.ZipFile(io.BytesIO(data)) as zf:
                        zf.extractall(vdir)
                except Exception:
                    pass

        checksum = self._dir_checksum(vdir)
        entry = {
            'version': next_version,
            'created_at': datetime.utcnow().isoformat() + 'Z',
            'files': sorted(self._list_files(vdir)),
            'metadata': metadata or {},
            'checksum': checksum
        }
        info['versions'].append(entry)
        self._write_meta(name, info)
        return entry

    def _dataset_dir(self, name: str) -> str:
        return os.path.join(self.base_dir, name)

    def _meta_path(self, name: str) -> str:
        return os.path.join(self._dataset_dir(name), 'dataset.json')

    def _read_meta(self, name: str) -> Optional[Dict]:
        path = self._meta_path(name)
        if not os.path.isfile(path):
            return None
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _write_meta(self, name: str, meta: Dict):
        with open(self._meta_path(name), 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

    def _next_version_id(self, info: Dict) -> str:
        if not info['versions']:
            return 'v0001'
        last = info['versions'][-1]['version']
        try:
            num = int(last.strip('v')) + 1
        except Exception:
            num = len(info['versions']) + 1
        return f"v{num:04d}"

    def _list_files(self, directory: str):
        files = []
        for root, _, fns in os.walk(directory):
            for fn in fns:
                rp = os.path.relpath(os.path.join(root, fn), directory)
                if rp == 'dataset.json':
                    continue
                files.append(rp)
        return files

    def _dir_checksum(self, directory: str) -> str:
        h = hashlib.sha256()
        for rel in sorted(self._list_files(directory)):
            p = os.path.join(directory, rel)
            h.update(rel.encode('utf-8'))
            with open(p, 'rb') as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    h.update(chunk)
        return h.hexdigest()

