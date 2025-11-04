import os
import re
import ast
import io
import tokenize
from typing import List, Dict

ENCODINGS = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']


def safe_read_text(path: str) -> str:
    if not os.path.exists(path):
        return ''
    size = os.path.getsize(path)
    if size == 0:
        return ''
    for enc in ENCODINGS:
        try:
            with open(path, 'r', encoding=enc, errors='ignore') as f:
                return f.read()
        except Exception:
            continue
    return ''


def split_markdown_sections(text: str) -> List[Dict]:
    lines = text.splitlines()
    sections: List[Dict] = []
    current = {"heading": None, "level": 0, "text": []}

    heading_re = re.compile(r'^(?P<hash>#{1,6})\s+(?P<title>.+?)\s*#*\s*$')

    def push_current():
        if current['heading'] is not None or current['text']:
            sections.append({
                'heading': current['heading'],
                'level': current['level'],
                'text': '\n'.join(current['text']).strip()
            })

    for line in lines:
        m = heading_re.match(line)
        if m:
            # new section
            push_current()
            current = {
                'heading': m.group('title').strip(),
                'level': len(m.group('hash')),
                'text': []
            }
        else:
            current['text'].append(line)
    push_current()

    # If no heading found, return empty to signal single-doc fallback
    has_headings = any(sec['heading'] for sec in sections)
    if not has_headings:
        return []
    return sections


def parse_python_file(path: str) -> List[Dict]:
    items: List[Dict] = []
    src = safe_read_text(path)
    if not src:
        return items
    # Parse AST for docstrings
    try:
        tree = ast.parse(src)
    except Exception:
        tree = None

    if tree is not None:
        mod_doc = ast.get_docstring(tree) or ''
        if mod_doc.strip():
            items.append({
                'type': 'docstring-module',
                'title': os.path.basename(path),
                'content': mod_doc.strip()
            })
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                doc = ast.get_docstring(node) or ''
                if doc.strip():
                    name = getattr(node, 'name', 'function')
                    items.append({
                        'type': 'docstring-function',
                        'title': name,
                        'content': doc.strip()
                    })
            elif isinstance(node, ast.ClassDef):
                doc = ast.get_docstring(node) or ''
                if doc.strip():
                    items.append({
                        'type': 'docstring-class',
                        'title': getattr(node, 'name', 'class'),
                        'content': doc.strip()
                    })
    # Tokenize comments
    try:
        tok_items = tokenize.generate_tokens(io.StringIO(src).readline)
        comments = []
        for tok in tok_items:
            if tok.type == tokenize.COMMENT:
                c = tok.string.lstrip('#').strip()
                if c:
                    comments.append(c)
        if comments:
            # chunk comments into paragraphs
            paragraph = []
            for c in comments:
                if c == '' and paragraph:
                    items.append({
                        'type': 'code-comment',
                        'title': os.path.basename(path),
                        'content': '\n'.join(paragraph).strip()
                    })
                    paragraph = []
                else:
                    paragraph.append(c)
            if paragraph:
                items.append({
                    'type': 'code-comment',
                    'title': os.path.basename(path),
                    'content': '\n'.join(paragraph).strip()
                })
    except Exception:
        pass

    return items


BLOCK_COMMENT_PATTERNS = [
    (re.compile(r'/\*([\s\S]*?)\*/'), lambda m: m.group(1)),  # /* ... */
]
LINE_COMMENT_PATTERNS = [
    re.compile(r'//(.*)$', re.M),  # // ...
    re.compile(r'#(.*)$', re.M),   # # ...
    re.compile(r';;(.*)$', re.M),  # ;; ... (Lisp)
]


def parse_code_comments_generic(text: str) -> List[str]:
    comments: List[str] = []
    # Block comments
    for pat, extract in BLOCK_COMMENT_PATTERNS:
        for m in pat.finditer(text):
            body = extract(m)
            comments.append(body.strip())
    # Line comments
    for pat in LINE_COMMENT_PATTERNS:
        for m in pat.finditer(text):
            comments.append(m.group(1).strip())
    return comments


LANG_BY_EXT = {
    '.py': 'python', '.js': 'javascript', '.ts': 'typescript', '.tsx': 'typescript', '.jsx': 'javascript',
    '.java': 'java', '.go': 'go', '.rb': 'ruby', '.php': 'php', '.rs': 'rust', '.swift': 'swift', '.kt': 'kotlin',
    '.c': 'c', '.h': 'c', '.hpp': 'cpp', '.cpp': 'cpp', '.cc': 'cpp', '.m': 'objective-c', '.mm': 'objective-c++',
    '.sh': 'shell', '.bash': 'shell', '.zsh': 'shell', '.ps1': 'powershell',
    '.scala': 'scala', '.sql': 'sql', '.lua': 'lua', '.r': 'r'
}


def guess_language_from_extension(ext: str) -> str:
    return LANG_BY_EXT.get(ext.lower(), 'code')

