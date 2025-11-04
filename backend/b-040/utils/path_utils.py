import os
import re


def safe_filename(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9\-_\. ]+", "", name)
    name = name.replace(" ", "-")
    return name or 'file'


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

