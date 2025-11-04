import os
import re
import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict


FILENAME_REGEX = re.compile(r"backup-(\d{8})(?:T|-)?(\d{6})(?:[\._-].+)?\.(?:bak|tar|zip|tgz|gz|bz2)$")


def _now_iso():
    return datetime.utcnow().isoformat() + 'Z'


def parse_backup_timestamp(filename: str):
    m = FILENAME_REGEX.match(filename)
    if not m:
        return None
    date_part, time_part = m.groups()
    s = f"{date_part}{time_part}"
    try:
        dt = datetime.strptime(s, '%Y%m%d%H%M%S')
        return dt
    except Exception:
        return None


def list_backups(backup_dir: str) -> List[Dict]:
    items = []
    Path(backup_dir).mkdir(parents=True, exist_ok=True)
    for entry in sorted(Path(backup_dir).glob('*')):
        if entry.is_file():
            ts = parse_backup_timestamp(entry.name)
            stat = entry.stat()
            created_dt = ts or datetime.utcfromtimestamp(stat.st_mtime)
            items.append({
                'name': entry.name,
                'path': str(entry.resolve()),
                'size': stat.st_size,
                'created_at': created_dt.isoformat() + 'Z',
                'hash_sha256': sha256_file(str(entry))
            })
    # sort by created_at ascending
    items.sort(key=lambda x: x['created_at'])
    return items


def create_dummy_backup(backup_dir: str, size_kb: int = 16, label: str = None):
    Path(backup_dir).mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    suffix = f"-{label}" if label else ''
    name = f"backup-{ts}{suffix}.bak"
    path = str(Path(backup_dir) / name)
    with open(path, 'wb') as f:
        chunk = os.urandom(1024)
        total = size_kb * 1024
        written = 0
        while written < total:
            to_write = min(1024, total - written)
            f.write(chunk[:to_write])
            written += to_write
    # update mtime for determinism
    os.utime(path, (time.time(), time.time()))
    return {
        'name': name,
        'path': path,
        'size': os.path.getsize(path),
        'created_at': _now_iso(),
        'hash_sha256': sha256_file(path)
    }


def delete_backup(path: str, base_dir: str):
    # Safety: ensure path is within base_dir
    base = str(Path(base_dir).resolve())
    target = str(Path(path).resolve())
    if not target.startswith(base + os.sep):
        raise ValueError('Refusing to delete file outside of backup_dir')
    if not os.path.isfile(target):
        raise FileNotFoundError('File not found')
    os.remove(target)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()

