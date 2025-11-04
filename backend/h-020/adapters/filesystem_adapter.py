import os
import re
from typing import Tuple

from models.wiki_content import WikiContent
from adapters.base import WikiAdapter, WikiAdapterError

class FilesystemAdapter(WikiAdapter):
    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        os.makedirs(self.root_dir, exist_ok=True)

    def _slugify(self, title: str) -> str:
        s = title.strip().lower()
        s = re.sub(r'\s+', '-', s)
        s = re.sub(r'[^a-z0-9\-_.]', '', s)
        return s or 'page'

    def _resolve_path(self, identifier: dict) -> str:
        path = identifier.get('path')
        if path:
            if os.path.isabs(path):
                raise WikiAdapterError("Filesystem path must be relative to root_dir")
            return os.path.join(self.root_dir, path)
        title = identifier.get('title') or 'page'
        slug = self._slugify(title)
        return os.path.join(self.root_dir, f"{slug}.md")

    def get_content(self, identifier: dict) -> WikiContent:
        abs_path = self._resolve_path(identifier)
        if not os.path.exists(abs_path):
            raise WikiAdapterError("Filesystem page not found", {"path": abs_path})
        with open(abs_path, 'r', encoding='utf-8') as f:
            text = f.read()
        title = identifier.get('title')
        if not title:
            # derive from first header
            m = re.match(r'^\s*#\s+(.+)$', text, flags=re.MULTILINE)
            if m:
                title = m.group(1).strip()
            else:
                title = os.path.basename(abs_path).rsplit('.', 1)[0]
        # strip leading H1 for pure content
        content = re.sub(r'^\s*#\s+.+\n+', '', text, count=1)
        return WikiContent(id=abs_path, title=title, markdown=content, source_url=f"file://{abs_path}")

    def upsert_content(self, identifier: dict, content: WikiContent) -> Tuple[dict, bool]:
        abs_path = self._resolve_path(identifier)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        created = not os.path.exists(abs_path)
        title = content.title or identifier.get('title') or 'Untitled'
        body = content.markdown or ''
        with open(abs_path, 'w', encoding='utf-8') as f:
            f.write(f"# {title}\n\n")
            f.write(body)
            if not body.endswith('\n'):
                f.write('\n')
        return ({'path': os.path.relpath(abs_path, self.root_dir)}, created)

