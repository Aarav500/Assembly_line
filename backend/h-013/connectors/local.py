import os
from typing import Optional

from .base import BaseConnector


class LocalConnector(BaseConnector):
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or '.'
        os.makedirs(self.base_dir, exist_ok=True)

    def write(self, content: bytes, path: str, content_type: Optional[str] = None) -> str:
        safe_path = os.path.normpath(path)
        if not os.path.isabs(safe_path):
            safe_path = os.path.join(self.base_dir, safe_path)
        # Ensure directory exists
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        with open(safe_path, 'wb') as f:
            f.write(content)
        return f"file://{os.path.abspath(safe_path)}"

