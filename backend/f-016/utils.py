import os
import re

def sanitize_filename(name: str) -> str:
    s = re.sub(r'[^A-Za-z0-9_.-]+', '_', name)
    if len(s) > 120:
        s = s[:120]
    return s.strip('_') or 'test'


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

