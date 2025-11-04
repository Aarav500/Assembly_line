import hashlib
import os
import zipfile


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_streamed(files_iter):
    """
    Compute a SHA256 over streamed chunks. files_iter yields bytes.
    """
    h = hashlib.sha256()
    for chunk in files_iter:
        if not chunk:
            continue
        h.update(chunk)
    return h.hexdigest()


def normalize_path(path: str) -> str:
    return path.replace('\\', '/').strip('/')


SAFE_EXTRACT_MAX_FILES = 20000
SAFE_EXTRACT_MAX_TOTAL_SIZE = 512 * 1024 * 1024  # 512MB


def safe_extract_zip(zip_path: str, target_dir: str):
    """
    Safely extract a zip archive to target_dir, preventing zip slip and
    excessive size extraction.
    """
    with zipfile.ZipFile(zip_path) as zf:
        members = zf.infolist()
        if len(members) > SAFE_EXTRACT_MAX_FILES:
            raise ValueError("too many files in archive")
        total_size = 0
        for info in members:
            # Prevent path traversal
            nm = info.filename
            if nm.startswith('/') or nm.startswith('\\'):
                raise ValueError("illegal absolute path in archive")
            norm = os.path.normpath(nm)
            if norm.startswith('..'):
                raise ValueError("illegal relative path in archive")

            total_size += info.file_size
            if total_size > SAFE_EXTRACT_MAX_TOTAL_SIZE:
                raise ValueError("archive too large to extract")

        for info in members:
            out_path = os.path.join(target_dir, info.filename)
            out_dir = os.path.dirname(out_path)
            os.makedirs(out_dir, exist_ok=True)
            if info.is_dir():
                os.makedirs(out_path, exist_ok=True)
            else:
                with zf.open(info, 'r') as src, open(out_path, 'wb') as dst:
                    while True:
                        chunk = src.read(8192)
                        if not chunk:
                            break
                        dst.write(chunk)


IGNORED_DIRS = {
    '.git', '.hg', '.svn', '.bzr',
    'node_modules', 'vendor', 'dist', 'build', 'target', 'out', 'bin',
    '__pycache__', '.mypy_cache', '.pytest_cache', '.tox', '.venv', 'venv',
    '.gradle', '.idea', '.vscode', '.DS_Store', '.cargo', 'Pods'
}


LANGUAGE_EXTENSIONS = {
    'py': 'Python',
    'js': 'JavaScript',
    'jsx': 'JavaScript',
    'ts': 'TypeScript',
    'tsx': 'TypeScript',
    'java': 'Java',
    'kt': 'Kotlin',
    'kts': 'Kotlin',
    'go': 'Go',
    'rs': 'Rust',
    'rb': 'Ruby',
    'php': 'PHP',
    'cs': 'C#',
    'c': 'C/C++',
    'cc': 'C/C++',
    'cpp': 'C/C++',
    'cxx': 'C/C++',
    'h': 'C/C++',
    'hpp': 'C/C++',
    'm': 'Objective-C',
    'mm': 'Objective-C++',
    'swift': 'Swift',
    'scala': 'Scala',
    'sc': 'Scala',
    'hs': 'Haskell',
    'lua': 'Lua',
    'pl': 'Perl',
    'pm': 'Perl',
    'sh': 'Shell',
    'bash': 'Shell',
    'ps1': 'PowerShell',
    'dart': 'Dart',
    'sql': 'SQL',
    'html': 'HTML',
    'htm': 'HTML',
    'css': 'CSS',
    'scss': 'Sass',
    'sass': 'Sass',
    'xml': 'XML',
    'json': 'JSON',
    'toml': 'TOML',
    'yaml': 'YAML',
    'yml': 'YAML',
    'md': 'Markdown',
    'rst': 'reStructuredText',
    'txt': 'Text'
}


KNOWN_MANIFESTS = [
    # Python
    'requirements.txt', 'requirements.in', 'pyproject.toml', 'Pipfile', 'Pipfile.lock', 'poetry.lock', 'setup.cfg', 'setup.py',
    # Node.js
    'package.json', 'package-lock.json', 'pnpm-lock.yaml', 'yarn.lock',
    # Java
    'pom.xml', 'build.gradle', 'build.gradle.kts', 'gradle.lockfile',
    # Go
    'go.mod', 'go.sum',
    # Rust
    'Cargo.toml', 'Cargo.lock',
    # PHP
    'composer.json', 'composer.lock',
    # Ruby
    'Gemfile', 'Gemfile.lock',
    # Swift/CocoaPods
    'Podfile', 'Podfile.lock'
]


def is_ignored_dir(name: str) -> bool:
    return name in IGNORED_DIRS or name.startswith('.')


def walk_files(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not is_ignored_dir(d)]
        for f in filenames:
            yield os.path.join(dirpath, f)


def fast_read_text(path: str, max_bytes: int = 5 * 1024 * 1024):
    with open(path, 'rb') as f:
        data = f.read(max_bytes)
    try:
        return data.decode('utf-8', errors='replace')
    except Exception:
        return data.decode('latin-1', errors='replace')


def file_ext(path: str) -> str:
    base = os.path.basename(path)
    if '.' not in base:
        return ''
    return base.rsplit('.', 1)[1].lower()


def detect_language_from_ext(path: str) -> str:
    ext = file_ext(path)
    return LANGUAGE_EXTENSIONS.get(ext, 'Other')


def safe_getsize(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0

