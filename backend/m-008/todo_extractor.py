import os
import re
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from flask import current_app
from models import db, BacklogItem


SUPPORTED_TAGS = ['TODO', 'FIXME', 'HACK', 'BUG', 'CHORE', 'NOTE']
TAG_PATTERN = re.compile(r"\b(?:(TODO|FIXME|HACK|BUG|CHORE|NOTE))(?:\([^)]*\))?[:\s\-]*([^\n\r]*)", re.IGNORECASE)


COMMENT_SYNTAX = {
    # line tokens, block tokens
    'py': (['#'], []),
    'rb': (['#'], []),
    'sh': (['#'], []),
    'bash': (['#'], []),
    'ps1': (['#'], []),
    'yaml': (['#'], []),
    'yml': (['#'], []),
    'toml': (['#'], []),
    'ini': ([';', '#'], []),
    'cfg': ([';', '#'], []),
    'conf': ([';', '#'], []),
    'sql': (['--'], [('/*', '*/')]),
    'js': (['//'], [('/*', '*/')]),
    'jsx': (['//'], [('/*', '*/')]),
    'ts': (['//'], [('/*', '*/')]),
    'tsx': (['//'], [('/*', '*/')]),
    'java': (['//'], [('/*', '*/')]),
    'kt': (['//'], [('/*', '*/')]),
    'c': (['//'], [('/*', '*/')]),
    'cc': (['//'], [('/*', '*/')]),
    'cpp': (['//'], [('/*', '*/')]),
    'cxx': (['//'], [('/*', '*/')]),
    'h': (['//'], [('/*', '*/')]),
    'hpp': (['//'], [('/*', '*/')]),
    'cs': (['//'], [('/*', '*/')]),
    'go': (['//'], [('/*', '*/')]),
    'rs': (['//'], [('/*', '*/')]),
    'php': (['//', '#'], [('/*', '*/')]),
    'swift': (['//'], [('/*', '*/')]),
    'html': ([], [('<!--', '-->')]),
    'xml': ([], [('<!--', '-->')]),
    'svg': ([], [('<!--', '-->')]),
    'vue': (['//'], [('/*', '*/'), ('<!--', '-->')]),
    'md': (['#', '>'], [('<!--', '-->')]),
    'txt': (['#'], [('<!--', '-->')]),
}


def is_binary_string(s: bytes) -> bool:
    # Heuristic: if NUL present or too many non-text bytes
    if b'\x00' in s:
        return True
    text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)))
    nontext = s.translate(None, text_chars)
    return float(len(nontext)) / max(1, len(s)) > 0.30


def read_text_file(path: Path) -> Optional[str]:
    try:
        with open(path, 'rb') as f:
            data = f.read()
            if is_binary_string(data):
                return None
        # Try utf-8 first, fallback to latin-1 with errors replaced
        try:
            return data.decode('utf-8')
        except UnicodeDecodeError:
            return data.decode('latin-1', errors='replace')
    except Exception:
        return None


def get_syntax(ext: str) -> Tuple[List[str], List[Tuple[str, str]]]:
    ext = (ext or '').lower()
    if ext.startswith('.'):
        ext = ext[1:]
    return COMMENT_SYNTAX.get(ext, (['#', '//'], [('/*', '*/'), ('<!--', '-->')]))


def normalize_text(s: str) -> str:
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    return s


def make_key(file_path: str, text: str) -> str:
    normalized = normalize_text(text).lower()
    h = hashlib.sha1()
    h.update((file_path + '|' + normalized).encode('utf-8'))
    return h.hexdigest()


def extract_todos_from_content(content: str, file_path: str) -> List[Dict]:
    ext = Path(file_path).suffix.lower().lstrip('.')
    line_tokens, block_tokens = get_syntax(ext)

    items: List[Dict] = []

    inside_block = False
    current_block_end = None

    # Build a regex to detect line comment tokens
    # We'll search each token's position and take substring after first occurrence
    for lineno, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.rstrip('\n')

        # Handle block comments
        if inside_block and current_block_end:
            end_idx = line.find(current_block_end)
            scan_segment = line if end_idx == -1 else line[:end_idx]
            for m in TAG_PATTERN.finditer(scan_segment):
                tag = m.group(1).upper()
                text = m.group(2).strip()
                items.append({'file_path': file_path, 'line_number': lineno, 'tag': tag, 'text': text if text else ''})
            if end_idx != -1:
                inside_block = False
                current_block_end = None
                # There could be another block starting later in the same line; simplistic approach ignores nested in same line
        # If not in a block, check for start of block
        if not inside_block and block_tokens:
            # Find earliest block start if present
            starts = [(line.find(start), start, end) for (start, end) in block_tokens if line.find(start) != -1]
            if starts:
                starts.sort(key=lambda t: t[0])
                idx, start_tok, end_tok = starts[0]
                # Scan comment content after start token for TODOs
                after = line[idx + len(start_tok):]
                # If end also present in this line
                end_idx = after.find(end_tok)
                scan_segment = after if end_idx == -1 else after[:end_idx]
                for m in TAG_PATTERN.finditer(scan_segment):
                    tag = m.group(1).upper()
                    text = m.group(2).strip()
                    items.append({'file_path': file_path, 'line_number': lineno, 'tag': tag, 'text': text if text else ''})
                if end_idx == -1:
                    inside_block = True
                    current_block_end = end_tok
                else:
                    inside_block = False
                    current_block_end = None
                # Continue to next line (still also check line comment tokens before block start?) For simplicity, skip
                continue

        # Handle line comments
        if line_tokens:
            # Find earliest occurrence of any line token
            positions = [(line.find(tok), tok) for tok in line_tokens if line.find(tok) != -1]
            if positions:
                positions.sort(key=lambda t: t[0])
                idx, tok = positions[0]
                comment = line[idx + len(tok):]
                m = TAG_PATTERN.search(comment)
                if m:
                    tag = m.group(1).upper()
                    text = m.group(2).strip()
                    items.append({'file_path': file_path, 'line_number': lineno, 'tag': tag, 'text': text if text else ''})
        else:
            # No explicit line token; scan whole line for HTML-like comments
            m = re.search(r'<!--(.*?)-->', line)
            if m:
                segment = m.group(1)
                for mm in TAG_PATTERN.finditer(segment):
                    tag = mm.group(1).upper()
                    text = mm.group(2).strip()
                    items.append({'file_path': file_path, 'line_number': lineno, 'tag': tag, 'text': text if text else ''})

    # Deduplicate same line occurrences (rare)
    seen = set()
    unique_items = []
    for it in items:
        k = (it['line_number'], it['tag'], it['text'])
        if k in seen:
            continue
        seen.add(k)
        unique_items.append(it)

    return unique_items


def should_exclude_dir(name: str, exclude_dirs: set) -> bool:
    return name in exclude_dirs or name.startswith('.') and name not in {'.', '..'} and name in exclude_dirs


def list_files(root: Path, include_exts: set, exclude_dirs: set, max_size: int) -> List[Path]:
    files: List[Path] = []
    for base, dirnames, filenames in os.walk(root):
        # Filter directories in-place to avoid walking into them
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for fname in filenames:
            path = Path(base) / fname
            ext = path.suffix.lower().lstrip('.')
            if ext not in include_exts:
                continue
            try:
                if path.stat().st_size > max_size:
                    continue
            except Exception:
                continue
            files.append(path)
    return files


def scan_files_for_todos(root: Path, include_exts: set, exclude_dirs: set, max_size: int) -> List[dict]:
    results: List[dict] = []
    root = root.resolve()
    for fpath in list_files(root, include_exts, exclude_dirs, max_size):
        rel_path = str(fpath.resolve().relative_to(root))
        content = read_text_file(fpath)
        if content is None:
            continue
        todos = extract_todos_from_content(content, rel_path)
        results.extend(todos)
    return results


def upsert_backlog_items(found_items: List[dict]):
    now = datetime.utcnow()

    # Load all existing items into dict by key for speed
    existing_by_key: Dict[str, BacklogItem] = {i.key: i for i in BacklogItem.query.all()}

    found_keys = set()
    new_count = 0
    updated_count = 0

    for it in found_items:
        file_path = it['file_path']
        line_number = it.get('line_number')
        tag = (it.get('tag') or 'TODO').upper()
        text = it.get('text') or ''
        key = make_key(file_path, f"{tag}: {text}")
        found_keys.add(key)

        if key in existing_by_key:
            item = existing_by_key[key]
            changed = False
            if item.file_path != file_path:
                item.file_path = file_path
                changed = True
            if item.line_number != line_number:
                item.line_number = line_number
                changed = True
            if item.text != text:
                item.text = text
                changed = True
            if item.tag != tag:
                item.tag = tag
                changed = True
            if item.status != 'open':
                item.status = 'open'
                changed = True
            item.last_seen_at = now
            if changed:
                item.updated_at = now
                updated_count += 1
        else:
            item = BacklogItem(
                key=key,
                file_path=file_path,
                line_number=line_number,
                text=text,
                tag=tag,
                status='open',
                first_seen_at=now,
                last_seen_at=now,
                updated_at=now,
            )
            db.session.add(item)
            new_count += 1

    # Resolve items no longer present
    open_items = BacklogItem.query.filter_by(status='open').all()
    resolved_count = 0
    for item in open_items:
        if item.key not in found_keys:
            item.status = 'resolved'
            item.updated_at = now
            item.last_seen_at = now
            resolved_count += 1

    db.session.commit()

    open_count = BacklogItem.query.filter_by(status='open').count()

    return {
        'new': new_count,
        'updated': updated_count,
        'resolved': resolved_count,
        'open': open_count,
    }


def scan_and_update_backlog(app) -> dict:
    with app.app_context():
        root = Path(app.config['SCAN_ROOT'])
        include_exts = set([e.lower().lstrip('.') for e in app.config['INCLUDE_EXTS']])
        exclude_dirs = set(app.config['EXCLUDE_DIRS'])
        max_size = int(app.config['MAX_FILE_SIZE_BYTES'])

        found_items = scan_files_for_todos(root, include_exts, exclude_dirs, max_size)
        result = upsert_backlog_items(found_items)
        result.update({'scanned': len(found_items)})
        return result

