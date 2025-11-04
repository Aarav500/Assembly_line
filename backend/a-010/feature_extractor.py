import os
import re
import json
import ast
from pathlib import Path
from typing import List, Dict, Any, Set


IGNORED_DIRS = {'.git', '.hg', '.svn', '__pycache__', 'node_modules', 'dist', 'build', '.venv', 'venv'}
CODE_EXTS = {'.py', '.js', '.ts', '.tsx', '.jsx', '.go', '.java', '.rb', '.php', '.rs', '.swift', '.kt'}
TEXT_EXTS = {'.md', '.txt', '.rst'}
FEATURE_FILE_NAMES = {'features.json', 'ideater.json'}


def _load_feature_file(path: Path) -> List[Dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if isinstance(data, dict) and 'features' in data:
            data = data['features']
        if not isinstance(data, list):
            return []
        features = []
        for item in data:
            if not isinstance(item, dict):
                continue
            title = item.get('title') or item.get('name') or 'Untitled Feature'
            desc = item.get('description') or item.get('desc') or ''
            kind = (item.get('kind') or item.get('type') or '').lower()
            if kind not in {'idea', 'component'}:
                # default heuristic
                kind = 'idea'
            tags = item.get('tags') or []
            features.append({
                'title': title,
                'description': desc,
                'kind': kind,
                'tags': list(set(['imported', 'declared'] + [t for t in tags if isinstance(t, str)])),
                'source_path': str(path.relative_to(path.parent.parent) if path.parent.parent else path.name)
            })
        return features
    except Exception:
        return []


def _extract_from_readme(path: Path) -> List[Dict[str, Any]]:
    text = ''
    try:
        text = path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return []
    features: List[Dict[str, Any]] = []

    # Patterns: headings that contain Feature or Component, and bullet lists under them
    heading_pattern = re.compile(r'^(#{1,6})\s*(Feature[s]?|Component[s]?|Idea[s]?)\b.*$', re.IGNORECASE | re.MULTILINE)
    bullet_pattern = re.compile(r'^[\-\*\+]\s+(.+)$', re.MULTILINE)

    for m in heading_pattern.finditer(text):
        section_start = m.end()
        next_heading = text.find('\n#', section_start)
        section = text[section_start: next_heading if next_heading != -1 else None]
        for b in bullet_pattern.finditer(section):
            line = b.group(1).strip()
            title = re.sub(r'[\.:]$', '', line.split(' - ')[0]).strip()
            desc = line
            kind = 'idea'
            if re.search(r'component', m.group(2), re.IGNORECASE) or re.search(r'\bcomponent\b', line, re.IGNORECASE):
                kind = 'component'
            features.append({
                'title': title[:120],
                'description': desc[:1000],
                'kind': kind,
                'tags': ['imported', 'discovered', 'readme'],
                'source_path': str(path.name)
            })

    # Inline annotations like: Feature: X, Component: Y, Idea: Z
    for line in text.splitlines():
        m = re.search(r'\b(Feature|Component|Idea)\s*:\s*(.+)$', line, re.IGNORECASE)
        if m:
            kind = m.group(1).lower()
            title = m.group(2).strip()
            features.append({
                'title': title[:120],
                'description': f'{kind.title()} from README: {title}'[:1000],
                'kind': 'component' if kind == 'component' else 'idea',
                'tags': ['imported', 'discovered', 'readme-inline'],
                'source_path': str(path.name)
            })

    return features


def _extract_from_code_comments(path: Path) -> List[Dict[str, Any]]:
    try:
        text = path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return []
    features: List[Dict[str, Any]] = []
    patterns = [
        re.compile(r'\bFeature\s*:\s*(.+)', re.IGNORECASE),
        re.compile(r'\bComponent\s*:\s*(.+)', re.IGNORECASE),
        re.compile(r'\bIdea\s*:\s*(.+)', re.IGNORECASE),
        re.compile(r'\bTODO\s*:\s*(.+)', re.IGNORECASE),
    ]
    for line in text.splitlines():
        for p in patterns:
            m = p.search(line)
            if m:
                key = p.pattern.split('\\s*')[0].strip('\\b').lower()
                content = m.group(1).strip()
                kind = 'idea'
                if 'component' in p.pattern.lower():
                    kind = 'component'
                features.append({
                    'title': content[:120],
                    'description': f'{key.title()} from {path.name}: {content}'[:1000],
                    'kind': kind,
                    'tags': ['imported', 'discovered', 'code-comment'],
                    'source_path': str(path.name)
                })
                break
    return features


def _extract_from_python_ast(path: Path) -> List[Dict[str, Any]]:
    try:
        src = path.read_text(encoding='utf-8', errors='ignore')
        tree = ast.parse(src)
    except Exception:
        return []
    features: List[Dict[str, Any]] = []

    class Visitor(ast.NodeVisitor):
        def add_feature(self, name: str, doc: str, node_type: str):
            if not doc:
                return
            # Heuristic: if doc contains 'component' -> component else idea
            kind = 'component' if re.search(r'\bcomponent\b', doc, re.IGNORECASE) else 'idea'
            title = f"{node_type} {name}"[:120]
            description = doc.strip().split('\n\n')[0][:1000]
            features.append({
                'title': title,
                'description': description,
                'kind': kind,
                'tags': ['imported', 'discovered', 'py-ast', node_type.lower()],
                'source_path': str(path.name)
            })

        def visit_ClassDef(self, node: ast.ClassDef):
            doc = ast.get_docstring(node)
            self.add_feature(node.name, doc or '', 'Class')
            self.generic_visit(node)

        def visit_FunctionDef(self, node: ast.FunctionDef):
            doc = ast.get_docstring(node)
            self.add_feature(node.name, doc or '', 'Function')
            self.generic_visit(node)

    Visitor().visit(tree)
    return features


def _normalize_features(features: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    seen_titles: Set[str] = set()
    for f in features:
        title = (f.get('title') or 'Untitled Feature').strip()
        if not title or title.lower() in seen_titles:
            continue
        seen_titles.add(title.lower())
        kind = f.get('kind', 'idea')
        if kind not in {'idea', 'component'}:
            kind = 'idea'
        desc = (f.get('description') or '').strip()
        tags = [t for t in (f.get('tags') or []) if isinstance(t, str)]
        tags = list(dict.fromkeys(['imported', 'discovered'] + tags))
        out.append({
            'title': title,
            'description': desc,
            'kind': kind,
            'tags': tags,
            'source_path': f.get('source_path') or ''
        })
    return out


def extract_features(project_dir: Path) -> List[Dict[str, Any]]:
    project_dir = Path(project_dir)
    if not project_dir.exists():
        return []
    
    collected: List[Dict[str, Any]] = []

    # First: look for declared feature files
    for name in FEATURE_FILE_NAMES:
        for p in project_dir.rglob(name):
            if any(part in IGNORED_DIRS for part in p.parts):
                continue
            collected.extend(_load_feature_file(p))

    # README files
    for p in project_dir.rglob('README*'):
        if any(part in IGNORED_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in TEXT_EXTS or p.suffix == '' or p.name.lower().startswith('readme'):
            collected.extend(_extract_from_readme(p))

    # Code comments and AST
    for p in project_dir.rglob('*'):
        if any(part in IGNORED_DIRS for part in p.parts):
            continue
        if p.is_file() and p.suffix in CODE_EXTS:
            collected.extend(_extract_from_code_comments(p))
            if p.suffix == '.py':
                collected.extend(_extract_from_python_ast(p))

    return _normalize_features(collected)
