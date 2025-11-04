import os
import re
from typing import List, Dict

from .parser_utils import (
    safe_read_text, split_markdown_sections, parse_python_file,
    parse_code_comments_generic, guess_language_from_extension
)
import config


class ProjectIndexer:
    def __init__(self):
        self.ignore_dirs = set(config.IGNORE_DIRS)
        self.doc_exts = set(config.DOC_EXTENSIONS)
        self.code_exts = set(config.CODE_EXTENSIONS)

    def _iter_files(self, root: str):
        for dirpath, dirnames, filenames in os.walk(root):
            # prune ignored directories
            dirnames[:] = [d for d in dirnames if d not in self.ignore_dirs and not d.startswith('.')]
            for fn in filenames:
                yield os.path.join(dirpath, fn)

    def _is_doc(self, path: str) -> bool:
        ext = os.path.splitext(path)[1].lower()
        return ext in self.doc_exts

    def _is_code(self, path: str) -> bool:
        ext = os.path.splitext(path)[1].lower()
        return ext in self.code_exts

    def index_path(self, root_path: str) -> List[Dict]:
        root_path = os.path.abspath(root_path)
        documents: List[Dict] = []
        doc_id = 0

        for path in self._iter_files(root_path):
            rel_path = os.path.relpath(path, root_path)
            if os.path.getsize(path) > config.MAX_FILE_BYTES:
                continue
            if self._is_doc(path):
                text = safe_read_text(path)
                if not text:
                    continue
                # Try to split into sections (for markdown/rst-like)
                sections = split_markdown_sections(text)
                if sections:
                    for sec in sections:
                        content = sec['text'].strip()
                        if not content:
                            continue
                        documents.append({
                            'id': doc_id,
                            'type': 'doc-section',
                            'title': sec['heading'] or os.path.basename(path),
                            'section_level': sec['level'],
                            'source_file': rel_path,
                            'language': 'text/markdown',
                            'content': content[:config.MAX_DOC_CHARS]
                        })
                        doc_id += 1
                else:
                    documents.append({
                        'id': doc_id,
                        'type': 'doc',
                        'title': os.path.basename(path),
                        'source_file': rel_path,
                        'language': 'text/plain',
                        'content': text[:config.MAX_DOC_CHARS]
                    })
                    doc_id += 1
            elif self._is_code(path):
                ext = os.path.splitext(path)[1].lower()
                language = guess_language_from_extension(ext)
                if ext == '.py':
                    parts = parse_python_file(path)
                    for p in parts:
                        documents.append({
                            'id': doc_id,
                            'type': p.get('type', 'code'),
                            'title': p.get('title') or os.path.basename(path),
                            'source_file': rel_path,
                            'language': language,
                            'content': p.get('content', '')[:config.MAX_DOC_CHARS]
                        })
                        doc_id += 1
                else:
                    text = safe_read_text(path)
                    if not text:
                        continue
                    comments = parse_code_comments_generic(text)
                    for c in comments:
                        content = c.strip()
                        if not content:
                            continue
                        documents.append({
                            'id': doc_id,
                            'type': 'code-comment',
                            'title': os.path.basename(path),
                            'source_file': rel_path,
                            'language': language,
                            'content': content[:config.MAX_DOC_CHARS]
                        })
                        doc_id += 1

        # Optionally, collapse README as high-priority docs
        prioritized = []
        for d in documents:
            if re.search(r'readme', d.get('source_file', ''), flags=re.I):
                d['priority'] = 2
            elif d['type'].startswith('doc'):
                d['priority'] = 1
            else:
                d['priority'] = 0
            prioritized.append(d)

        return prioritized

