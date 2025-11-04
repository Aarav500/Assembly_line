import os
import json
from typing import Dict, List, Tuple
from .utils import walk_files, KNOWN_MANIFESTS, normalize_path, sha256_hex, detect_language_from_ext, safe_getsize
from .parsers import (
    parse_python_requirements_txt,
    parse_python_pyproject_toml,
    parse_python_pipfile_lock,
    parse_python_poetry_lock,
    parse_node_package_json,
    parse_node_package_lock_json,
    parse_rust_cargo_lock,
    parse_rust_cargo_toml,
    parse_go_mod,
    parse_java_pom_xml,
    parse_gradle_lockfile,
    parse_php_composer_lock,
)


def gather_manifests(root: str) -> List[str]:
    manifests: List[str] = []
    known = set(KNOWN_MANIFESTS)
    for path in walk_files(root):
        base = os.path.basename(path)
        if base in known:
            rel = normalize_path(os.path.relpath(path, root))
            manifests.append(rel)
    manifests.sort()
    return manifests


def compute_manifest_hash(root: str, manifests: List[str]) -> str:
    if not manifests:
        # Fallback: hash of top-level file names and sizes
        entries: List[Tuple[str, int]] = []
        for path in walk_files(root):
            rel = normalize_path(os.path.relpath(path, root))
            size = safe_getsize(path)
            entries.append((rel, size))
        entries.sort()
        blob = ''.join(f"{rel}\t{size}\n" for rel, size in entries).encode('utf-8')
        return sha256_hex(blob)

    chunks: List[bytes] = []
    for rel in manifests:
        abs_path = os.path.join(root, rel)
        try:
            with open(abs_path, 'rb') as f:
                data = f.read()
        except Exception:
            data = b''
        chunks.append(rel.encode('utf-8') + b"\n")
        chunks.append(data)
        chunks.append(b"\n--\n")
    return sha256_hex(b''.join(chunks))


def analyze_languages(root: str) -> Dict:
    totals: Dict[str, int] = {}
    file_counts: Dict[str, int] = {}
    for path in walk_files(root):
        lang = detect_language_from_ext(path)
        size = safe_getsize(path)
        totals[lang] = totals.get(lang, 0) + size
        file_counts[lang] = file_counts.get(lang, 0) + 1

    # Build list and compute fingerprint hash
    langs = []
    for lang, bytes_count in totals.items():
        langs.append({"language": lang, "bytes": bytes_count, "files": file_counts.get(lang, 0)})
    langs.sort(key=lambda x: (-x['bytes'], x['language']))

    desc = ','.join(f"{e['language']}:{e['bytes']}" for e in langs)
    fp = sha256_hex(desc.encode('utf-8'))

    return {
        "languages": langs,
        "language_fingerprint": fp,
    }


def analyze_dependencies(root: str, manifests: List[str]) -> Dict:
    eco: Dict[str, List[Dict]] = {}

    def add(ecosystem: str, items: List[Dict]):
        if not items:
            return
        eco.setdefault(ecosystem, []).extend(items)

    for rel in manifests:
        abs_path = os.path.join(root, rel)
        base = os.path.basename(rel)
        try:
            if base == 'requirements.txt' or base == 'requirements.in':
                add('python', parse_python_requirements_txt(abs_path))
            elif base == 'pyproject.toml':
                add('python', parse_python_pyproject_toml(abs_path))
            elif base == 'Pipfile.lock':
                add('python', parse_python_pipfile_lock(abs_path))
            elif base == 'poetry.lock':
                add('python', parse_python_poetry_lock(abs_path))
            elif base == 'package.json':
                add('node', parse_node_package_json(abs_path))
            elif base == 'package-lock.json':
                add('node', parse_node_package_lock_json(abs_path))
            elif base == 'Cargo.lock':
                add('rust', parse_rust_cargo_lock(abs_path))
            elif base == 'Cargo.toml':
                add('rust', parse_rust_cargo_toml(abs_path))
            elif base == 'go.mod':
                add('go', parse_go_mod(abs_path))
            elif base == 'pom.xml':
                add('maven', parse_java_pom_xml(abs_path))
            elif base == 'gradle.lockfile':
                add('gradle', parse_gradle_lockfile(abs_path))
            elif base == 'composer.lock':
                add('php', parse_php_composer_lock(abs_path))
        except Exception:
            # Best-effort parsing; ignore individual file parse errors
            continue

    # Dependency fingerprint: sorted canonical string of ecosystem:name@version|spec
    normalized_entries: List[str] = []
    for eco_name, deps in eco.items():
        for d in deps:
            nm = str(d.get('name'))
            ver = d.get('version') or ''
            spec = d.get('spec') or ''
            normalized_entries.append(f"{eco_name}:{nm}@{ver}|{spec}")
    normalized_entries.sort()
    dep_fp = sha256_hex('\n'.join(normalized_entries).encode('utf-8')) if normalized_entries else None

    return {
        "ecosystems": eco,
        "dependency_fingerprint": dep_fp
    }


def analyze_directory(root: str) -> Dict:
    manifests = gather_manifests(root)
    manifest_hash = compute_manifest_hash(root, manifests)
    lang_info = analyze_languages(root)
    dep_info = analyze_dependencies(root, manifests)

    # Project fingerprint combines core components
    combo_str = '\n'.join([
        f"manifest:{manifest_hash}",
        f"languages:{lang_info['language_fingerprint']}",
        f"dependencies:{dep_info.get('dependency_fingerprint') or ''}",
    ])
    project_fp = sha256_hex(combo_str.encode('utf-8'))

    return {
        "manifests": manifests,
        "manifest_hash": manifest_hash,
        "languages": lang_info["languages"],
        "language_fingerprint": lang_info["language_fingerprint"],
        "dependencies": dep_info["ecosystems"],
        "dependency_fingerprint": dep_info["dependency_fingerprint"],
        "project_fingerprint": project_fp,
    }

