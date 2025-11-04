import os
from pathlib import Path
from typing import List, Dict, Any, Tuple


ALLOWED_TEXT_ENCODINGS = ['utf-8']


def sanitize_relative_path(path: str) -> Path:
    p = Path(path)
    # Disallow absolute paths and parent traversal
    if p.is_absolute():
        raise ValueError(f'Absolute paths are not allowed: {path}')
    normalized = Path(os.path.normpath(str(p)))
    parts = list(normalized.parts)
    if any(part in ('..',) for part in parts):
        raise ValueError(f'Path traversal detected: {path}')
    return normalized


def write_files_to_directory(base_dir: Path, files: List[Dict[str, Any]]) -> None:
    for f in files:
        rel = sanitize_relative_path(f.get('path', ''))
        if not rel or rel.as_posix().strip() == '':
            raise ValueError('Empty file path in files array')
        full = (base_dir / rel).resolve()
        full.parent.mkdir(parents=True, exist_ok=True)
        content = f.get('content', '')
        # Write as text
        with open(full, 'w', encoding='utf-8', newline='') as fp:
            fp.write(content)


def validate_files_schema(payload: Dict[str, Any], max_files: int, max_total_bytes: int) -> None:
    if not isinstance(payload, dict):
        raise ValueError('Payload must be a JSON object')
    files = payload.get('files')
    if not isinstance(files, list):
        raise ValueError('Payload must contain a list "files"')
    if len(files) == 0:
        raise ValueError('No files returned')
    if len(files) > max_files:
        raise ValueError(f'Too many files: {len(files)} > {max_files}')
    total = 0
    seen = set()
    for i, f in enumerate(files):
        if not isinstance(f, dict):
            raise ValueError(f'File entry at index {i} must be an object')
        path = f.get('path')
        content = f.get('content')
        if not isinstance(path, str) or not path.strip():
            raise ValueError(f'File at index {i} missing valid "path"')
        if not isinstance(content, str):
            raise ValueError(f'File at index {i} missing string "content"')
        norm = sanitize_relative_path(path).as_posix()
        if norm in seen:
            raise ValueError(f'Duplicate file path: {norm}')
        seen.add(norm)
        total += len(content.encode('utf-8'))
        if total > max_total_bytes:
            raise ValueError(f'Total content too large (> {max_total_bytes} bytes)')


def summarize_files(files: List[Dict[str, Any]]):
    res = []
    for f in files:
        content = f.get('content', '')
        res.append({
            'path': sanitize_relative_path(f.get('path', '')).as_posix(),
            'bytes': len(content.encode('utf-8')),
        })
    return res

