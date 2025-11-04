import json
import os
import re
import xml.etree.ElementTree as ET
from typing import List, Dict

try:
    import tomllib as toml  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as toml  # type: ignore

from .utils import fast_read_text

NAME_CLEAN_RE = re.compile(r"[^A-Za-z0-9_.\-]++", re.UNICODE)


def normalize_name(name: str) -> str:
    return NAME_CLEAN_RE.sub('-', name.strip()).strip('-').lower()


# ---------------- Python ----------------

def parse_python_requirements_txt(path: str) -> List[Dict]:
    deps: List[Dict] = []
    text = fast_read_text(path)
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('-r') or line.startswith('--'):
            continue
        # git or url spec
        if '://' in line or line.startswith('git+'):
            name = line
            deps.append({"name": name, "version": None, "spec": line, "source": os.path.basename(path)})
            continue
        # PEP 440 simple parse: name[extra] op version ; markers
        # Extract name up to first space or comparison operator
        m = re.match(r"([^;<>=!~\s]+)\s*([<>=!~]=?|===)?\s*([^;\s]+)?", line)
        if m:
            raw_name = m.group(1)
            spec_op = m.group(2) or ''
            spec_ver = m.group(3) or ''
            name = normalize_name(raw_name.split('[')[0])
            spec = (spec_op + spec_ver).strip() if (spec_op or spec_ver) else ''
            version = None
            if spec.startswith('=='):
                version = spec[2:]
            deps.append({"name": name, "version": version, "spec": spec or None, "source": os.path.basename(path)})
    return deps


def parse_python_pyproject_toml(path: str) -> List[Dict]:
    deps: List[Dict] = []
    with open(path, 'rb') as f:
        data = toml.load(f)
    # PEP 621
    project = data.get('project') or {}
    def _consume(dep_entry):
        if isinstance(dep_entry, str):
            # Format like "package >=1.2"
            m = re.match(r"([^;<>=!~\s]+)\s*([<>=!~]=?|===)?\s*([^;\s]+)?", dep_entry)
            if m:
                name = normalize_name(m.group(1).split('[')[0])
                op = m.group(2) or ''
                ver = m.group(3) or ''
                spec = (op + ver).strip() if (op or ver) else None
                version = ver if op == '==' else None
                deps.append({"name": name, "version": version, "spec": spec, "source": 'pyproject.toml'})
        elif isinstance(dep_entry, dict):
            name = normalize_name(dep_entry.get('name') or dep_entry.get('package', ''))
            if name:
                version = dep_entry.get('version')
                spec = version
                deps.append({"name": name, "version": version, "spec": spec, "source": 'pyproject.toml'})

    for dep in project.get('dependencies') or []:
        _consume(dep)
    opt = project.get('optional-dependencies') or {}
    for group, group_deps in opt.items():
        for dep in group_deps or []:
            _consume(dep)

    # Poetry tool tables
    tool = data.get('tool') or {}
    poetry = tool.get('poetry') or {}
    def _consume_poetry_table(tbl):
        for name, val in (tbl or {}).items():
            nm = normalize_name(name)
            version = None
            spec = None
            if isinstance(val, str):
                spec = val
                if spec.startswith('^') or spec.startswith('~'):
                    version = None
                else:
                    # optimistic: exact if starts with == or digits only
                    m = re.match(r"\d+", spec)
                    if m:
                        version = spec
            elif isinstance(val, dict):
                version = val.get('version')
                spec = version
            deps.append({"name": nm, "version": version, "spec": spec, "source": 'pyproject.toml'})

    _consume_poetry_table(poetry.get('dependencies'))
    _consume_poetry_table(poetry.get('dev-dependencies'))
    groups = poetry.get('group') or {}
    for gname, gtbl in groups.items():
        _consume_poetry_table((gtbl or {}).get('dependencies'))

    return deps


def parse_python_pipfile_lock(path: str) -> List[Dict]:
    deps: List[Dict] = []
    data = json.loads(fast_read_text(path))
    for section in ('default', 'develop'):
        sec = data.get(section) or {}
        for name, meta in sec.items():
            nm = normalize_name(name)
            version = None
            spec = None
            if isinstance(meta, dict):
                version = (meta.get('version') or '').lstrip('=') if meta.get('version') else None
                spec = meta.get('version')
            elif isinstance(meta, str):
                spec = meta
                version = meta.lstrip('=') if meta.startswith('==') else None
            deps.append({"name": nm, "version": version, "spec": spec, "source": 'Pipfile.lock'})
    return deps


def parse_python_poetry_lock(path: str) -> List[Dict]:
    deps: List[Dict] = []
    with open(path, 'rb') as f:
        data = toml.load(f)
    for pkg in data.get('package') or []:
        name = normalize_name(pkg.get('name', ''))
        version = pkg.get('version')
        if name:
            deps.append({"name": name, "version": version, "spec": version, "source": 'poetry.lock'})
    return deps


# ---------------- Node.js ----------------

def parse_node_package_json(path: str) -> List[Dict]:
    deps: List[Dict] = []
    data = json.loads(fast_read_text(path))
    for sec in ('dependencies', 'devDependencies', 'peerDependencies', 'optionalDependencies'):
        sec_map = data.get(sec) or {}
        for name, spec in sec_map.items():
            deps.append({"name": name, "version": None, "spec": str(spec), "source": f"package.json:{sec}"})
    return deps


def parse_node_package_lock_json(path: str) -> List[Dict]:
    deps: List[Dict] = []
    data = json.loads(fast_read_text(path))
    if 'packages' in data:
        # npm v7+
        for pkg_path, meta in (data.get('packages') or {}).items():
            name = meta.get('name')
            version = meta.get('version')
            if name and pkg_path != '':  # skip root
                deps.append({"name": name, "version": version, "spec": version, "source": 'package-lock.json'})
    elif 'dependencies' in data:
        def walk_deps(dct):
            for name, meta in dct.items():
                version = meta.get('version') if isinstance(meta, dict) else None
                deps.append({"name": name, "version": version, "spec": version, "source": 'package-lock.json'})
                if isinstance(meta, dict) and 'dependencies' in meta:
                    walk_deps(meta['dependencies'])
        walk_deps(data['dependencies'])
    return deps


# ---------------- Rust ----------------

def parse_rust_cargo_lock(path: str) -> List[Dict]:
    deps: List[Dict] = []
    with open(path, 'rb') as f:
        data = toml.load(f)
    for pkg in data.get('package') or []:
        name = pkg.get('name')
        version = pkg.get('version')
        if name:
            deps.append({"name": name, "version": version, "spec": version, "source": 'Cargo.lock'})
    return deps


def parse_rust_cargo_toml(path: str) -> List[Dict]:
    deps: List[Dict] = []
    with open(path, 'rb') as f:
        data = toml.load(f)
    for sec in ('dependencies', 'dev-dependencies', 'build-dependencies'):
        sec_map = data.get(sec) or {}
        if not isinstance(sec_map, dict):
            continue
        for name, val in sec_map.items():
            version = None
            spec = None
            if isinstance(val, str):
                spec = val
                version = val if re.match(r"^\d+", val) else None
            elif isinstance(val, dict):
                version = val.get('version')
                spec = version
            deps.append({"name": name, "version": version, "spec": spec, "source": f"Cargo.toml:{sec}"})
    return deps


# ---------------- Go ----------------

def parse_go_mod(path: str) -> List[Dict]:
    deps: List[Dict] = []
    text = fast_read_text(path)
    in_require = False
    for line in text.splitlines():
        line = line.strip()
        if line.startswith('require ('):
            in_require = True
            continue
        if in_require:
            if line == ')':
                in_require = False
                continue
            # Format: module version [// indirect]
            parts = line.split()
            if len(parts) >= 2:
                name = parts[0]
                version = parts[1]
                deps.append({"name": name, "version": version, "spec": version, "source": 'go.mod'})
        elif line.startswith('require '):
            parts = line[8:].split()
            if len(parts) >= 2:
                name = parts[0]
                version = parts[1]
                deps.append({"name": name, "version": version, "spec": version, "source": 'go.mod'})
    return deps


# ---------------- Java/Maven ----------------

def parse_java_pom_xml(path: str) -> List[Dict]:
    deps: List[Dict] = []
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        ns = {'m': 'http://maven.apache.org/POM/4.0.0'}
        for dep in root.findall('.//m:dependency', ns):
            group_id = dep.find('m:groupId', ns)
            artifact_id = dep.find('m:artifactId', ns)
            version_el = dep.find('m:version', ns)
            if group_id is not None and artifact_id is not None:
                name = f"{group_id.text}:{artifact_id.text}"
                version = version_el.text if version_el is not None else None
                deps.append({"name": name, "version": version, "spec": version, "source": 'pom.xml'})
    except Exception:
        pass
    return deps


def parse_gradle_lockfile(path: str) -> List[Dict]:
    deps: List[Dict] = []
    text = fast_read_text(path)
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        # Format: group:artifact:version=...
        parts = line.split('=')
        if len(parts) >= 1:
            coord = parts[0]
            coord_parts = coord.split(':')
            if len(coord_parts) >= 3:
                name = f"{coord_parts[0]}:{coord_parts[1]}"
                version = coord_parts[2]
                deps.append({"name": name, "version": version, "spec": version, "source": 'gradle.lockfile'})
    return deps


# ---------------- PHP ----------------

def parse_php_composer_lock(path: str) -> List[Dict]:
    deps: List[Dict] = []
    data = json.loads(fast_read_text(path))
    for section in ('packages', 'packages-dev'):
        packages = data.get(section) or []
        for pkg in packages:
            name = pkg.get('name')
            version = pkg.get('version')
            if name:
                deps.append({"name": name, "version": version, "spec": version, "source": 'composer.lock'})
    return deps
