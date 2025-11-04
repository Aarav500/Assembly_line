import os
import io
import re
import json
from typing import Optional, Dict

import requests
from bs4 import BeautifulSoup
from pdfminer.high_level import extract_text as pdf_extract_text
from docx import Document as DocxDocument


TEXT_EXTENSIONS = {
    'txt', 'md', 'json', 'yaml', 'yml', 'toml', 'csv', 'ini', 'env', 'log',
}

CODE_EXTENSIONS = {
    'py', 'js', 'ts', 'tsx', 'jsx', 'java', 'go', 'rb', 'php', 'cpp', 'c', 'h', 'hpp', 'cs', 'rs', 'html', 'css', 'sh', 'sql', 'kt'
}


def _is_binary_file(path: str, sample_size: int = 2048) -> bool:
    try:
        with open(path, 'rb') as f:
            chunk = f.read(sample_size)
            if b'\x00' in chunk:
                return True
            # Heuristic: if too many non-text bytes
            text_chars = bytearray({7,8,9,10,12,13,27} | set(range(0x20, 0x100)))
            nontext = chunk.translate(None, text_chars)
            return float(len(nontext)) / max(1, len(chunk)) > 0.30
    except Exception:
        return True


def _guess_mime_by_ext(ext: str) -> str:
    ext = ext.lower().lstrip('.')
    if ext == 'pdf':
        return 'application/pdf'
    if ext == 'docx':
        return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    if ext in ('html', 'htm'):
        return 'text/html'
    return 'text/plain'


def extract_text_from_file(path: str) -> Optional[Dict]:
    """
    Extract text from a local file by extension.
    Returns dict with keys: title, content, mime, meta
    """
    if not os.path.exists(path):
        return None

    ext = os.path.splitext(path)[1].lower().lstrip('.')

    if ext == 'pdf':
        try:
            text = pdf_extract_text(path) or ''
            title = os.path.basename(path)
            return {
                'title': title,
                'content': text.strip(),
                'mime': _guess_mime_by_ext(ext),
                'meta': {'extension': ext}
            }
        except Exception as e:
            raise e

    if ext == 'docx':
        try:
            doc = DocxDocument(path)
            paras = [p.text for p in doc.paragraphs if p.text]
            text = '\n'.join(paras)
            props_title = None
            try:
                props_title = doc.core_properties.title
            except Exception:
                props_title = None
            title = props_title or os.path.basename(path)
            return {
                'title': title,
                'content': text.strip(),
                'mime': _guess_mime_by_ext(ext),
                'meta': {'extension': ext}
            }
        except Exception as e:
            raise e

    # treat as text/code if extension is known
    if ext in TEXT_EXTENSIONS or ext in CODE_EXTENSIONS:
        if _is_binary_file(path):
            return None
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        return {
            'title': os.path.basename(path),
            'content': content.strip(),
            'mime': _guess_mime_by_ext(ext),
            'meta': {'extension': ext}
        }

    # Fallback: try to read as text
    try:
        if _is_binary_file(path):
            return None
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        return {
            'title': os.path.basename(path),
            'content': content.strip(),
            'mime': 'text/plain',
            'meta': {'extension': ext}
        }
    except Exception as e:
        raise e


def extract_from_url(url: str, timeout: int = 20) -> Optional[Dict]:
    """Download and extract text from a web page URL"""
    headers = {
        'User-Agent': 'DocIngestBot/1.0 (+https://example.com)'
    }
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()

    content_type = resp.headers.get('Content-Type', '')

    if 'text/html' in content_type or url.lower().endswith(('.html', '.htm')):
        soup = BeautifulSoup(resp.text, 'html.parser')
        for tag in soup(['script', 'style', 'noscript']):
            tag.decompose()
        title = None
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        # Remove nav/footer/header if present
        for tag in soup.find_all(['nav', 'header', 'footer', 'aside']):
            tag.decompose()
        text = soup.get_text('\n')
        lines = [l.strip() for l in text.splitlines()]
        chunks = [l for l in lines if l]
        body = '\n'.join(chunks)
        return {
            'title': title or url,
            'content': body.strip(),
            'mime': 'text/html',
            'meta': {
                'url': url,
                'content_type': content_type
            }
        }

    # For PDFs or other content types, try to handle minimal cases
    if 'application/pdf' in content_type or url.lower().endswith('.pdf'):
        # Save to memory then parse
        with io.BytesIO(resp.content) as mem:
            tmp_path = url.split('/')[-1] or 'download.pdf'
            # pdfminer requires a file path or file-like? high_level.extract_text supports path or file-like
            # But for consistent behavior, write to temp file on disk
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=True) as tf:
                tf.write(mem.getvalue())
                tf.flush()
                text = pdf_extract_text(tf.name) or ''
                return {
                    'title': tmp_path,
                    'content': text.strip(),
                    'mime': 'application/pdf',
                    'meta': {
                        'url': url,
                        'content_type': content_type
                    }
                }

    # Fallback to plain text
    try:
        text = resp.text
    except Exception:
        text = ''
    return {
        'title': url,
        'content': text.strip(),
        'mime': content_type or 'text/plain',
        'meta': {'url': url, 'content_type': content_type}
    }


def extract_code_file(path: str) -> Optional[Dict]:
    ext = os.path.splitext(path)[1].lower().lstrip('.')
    if _is_binary_file(path):
        return None
    if ext not in CODE_EXTENSIONS and ext not in TEXT_EXTENSIONS:
        return None
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    return {
        'title': os.path.basename(path),
        'content': content,
        'mime': 'text/plain',
        'meta': {'extension': ext}
    }

