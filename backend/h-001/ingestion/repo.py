import os
import shutil
import tempfile
from typing import List, Optional, Dict
from datetime import datetime

from git import Repo

from .parsers import extract_code_file


DEFAULT_INCLUDE_EXT = [
    'py','js','ts','tsx','jsx','java','go','rb','php','cpp','c','h','hpp','cs','rs','html','css','md','txt','json','yml','yaml','toml','sh','sql','kt'
]
DEFAULT_EXCLUDE_DIRS = ['.git', 'node_modules', 'dist', 'build', 'out', 'target', '__pycache__', '.next', '.venv', 'venv']


def _iter_files(root: str, include_ext: List[str], exclude_dirs: List[str], max_files: Optional[int]=None):
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower().lstrip('.')
            if ext in include_ext:
                full = os.path.join(dirpath, fname)
                yield full
                count += 1
                if max_files and count >= max_files:
                    return


def clone_and_extract_repo(repo_url: str, base_dir: str, branch: Optional[str]=None,
                            include_ext: Optional[List[str]]=None, exclude_dirs: Optional[List[str]]=None,
                            max_files: Optional[int]=None) -> Dict:
    os.makedirs(base_dir, exist_ok=True)

    # Create unique directory name based on repo URL and timestamp
    safe_name = repo_url.rstrip('/').split('/')[-1].replace('.git', '') or 'repo'
    timestamp = datetime.utcnow().strftime('%Y%m%dT%H%M%S')
    local_path = os.path.join(base_dir, f"{safe_name}_{timestamp}")

    repo = Repo.clone_from(repo_url, local_path)
    if branch:
        repo.git.checkout(branch)

    head_commit = repo.head.commit.hexsha if repo.head and repo.head.commit else ''

    include = include_ext or DEFAULT_INCLUDE_EXT
    exclude = exclude_dirs or DEFAULT_EXCLUDE_DIRS

    files_data = []
    root = local_path
    for path in _iter_files(root, include, exclude, max_files=max_files):
        rel = os.path.relpath(path, root)
        parsed = extract_code_file(path)
        if not parsed or not parsed.get('content'):
            continue
        files_data.append({
            'relative_path': rel,
            'content': parsed.get('content'),
            'language': os.path.splitext(path)[1].lstrip('.').lower(),
        })

    return {
        'local_path': local_path,
        'branch': branch or repo.active_branch.name if not repo.head.is_detached else branch or 'detached',
        'commit': head_commit,
        'files': files_data
    }

