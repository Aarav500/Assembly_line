import logging
import os
import shutil
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


def _run_git(cwd: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    cmd = ["git", *args]
    logger.debug("Running: %s (cwd=%s)", " ".join(cmd), cwd)

    env = os.environ.copy()
    # Ensure colors do not pollute outputs
    env["GIT_PAGER"] = "cat"
    env["GIT_TERMINAL_PROMPT"] = "0"

    cp = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if check and cp.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {cp.stderr.strip()}".strip())
    return cp


def is_git_repo(path: str) -> bool:
    try:
        cp = _run_git(path, "rev-parse", "--is-inside-work-tree", check=False)
        return cp.returncode == 0 and cp.stdout.strip() == "true"
    except Exception:
        return False


def init_repo_if_needed(path: str) -> None:
    if is_git_repo(path):
        return
    # Initialize repo if not exists
    _run_git(path, "init")
    # Default branch main if possible
    try:
        _run_git(path, "symbolic-ref", "HEAD", "refs/heads/main")
    except Exception:
        pass
    ensure_repo_config(path)


def ensure_repo_config(path: str) -> None:
    # Ensure user.name and user.email are configured
    name = os.getenv("GIT_AUTHOR_NAME") or os.getenv("GIT_COMMITTER_NAME") or "Auto Sync Bot"
    email = os.getenv("GIT_AUTHOR_EMAIL") or os.getenv("GIT_COMMITTER_EMAIL") or "autosync@example.com"

    try:
        cp = _run_git(path, "config", "--get", "user.name", check=False)
        if cp.returncode != 0 or not cp.stdout.strip():
            _run_git(path, "config", "user.name", name)
    except Exception:
        _run_git(path, "config", "user.name", name)

    try:
        cp = _run_git(path, "config", "--get", "user.email", check=False)
        if cp.returncode != 0 or not cp.stdout.strip():
            _run_git(path, "config", "user.email", email)
    except Exception:
        _run_git(path, "config", "user.email", email)


def get_current_branch(path: str) -> Optional[str]:
    cp = _run_git(path, "rev-parse", "--abbrev-ref", "HEAD", check=False)
    b = cp.stdout.strip()
    if cp.returncode != 0 or b == "HEAD" or not b:
        return None
    return b


def has_changes(path: str) -> bool:
    cp = _run_git(path, "status", "--porcelain", check=False)
    return bool(cp.stdout.strip())


def git_add_all(path: str) -> None:
    _run_git(path, "add", "-A")


def git_commit(path: str, message: str) -> bool:
    cp = _run_git(path, "commit", "-m", message, check=False)
    if cp.returncode != 0:
        # No changes to commit or error; try to detect benign case
        if "nothing to commit" in (cp.stdout + cp.stderr).lower():
            return False
        raise RuntimeError(cp.stderr.strip() or cp.stdout.strip() or "git commit failed")
    return True


def git_push(path: str, remote: str, branch: Optional[str]) -> bool:
    # If no upstream set, set upstream
    if branch is None:
        branch = get_current_branch(path)
    if branch is None:
        raise RuntimeError("Cannot determine branch to push")

    # Check if upstream exists; if not, push with -u
    has_upstream = False
    cp = _run_git(path, "rev-parse", "--abbrev-ref", f"{branch}@{{upstream}}", check=False)
    if cp.returncode == 0 and cp.stdout.strip():
        has_upstream = True

    args = ["push"]
    if not has_upstream:
        args.append("-u")
    args += [remote, branch]
    cp2 = _run_git(path, *args, check=False)

    if cp2.returncode != 0:
        # Attempt to create remote if URL provided via env GIT_REMOTE_URL
        remote_url = os.getenv("GIT_REMOTE_URL")
        if remote_url and "No such remote" in cp2.stderr:
            _run_git(path, "remote", "add", remote, remote_url)
            cp2 = _run_git(path, *args, check=False)

    if cp2.returncode != 0:
        raise RuntimeError(cp2.stderr.strip() or cp2.stdout.strip() or "git push failed")
    return True


def git_pull(path: str, remote: str, branch: str) -> str:
    cp = _run_git(path, "pull", "--rebase", remote, branch, check=False)
    if cp.returncode != 0:
        # handle first pull when upstream not set
        if "no such ref was found" in (cp.stderr + cp.stdout).lower() or "no tracking information" in (cp.stderr + cp.stdout).lower():
            # set upstream by pushing empty tree or simply set upstream without push
            try:
                _run_git(path, "branch", "--set-upstream-to", f"{remote}/{branch}", branch)
            except Exception:
                pass
            cp = _run_git(path, "pull", "--rebase", remote, branch, check=False)
    if cp.returncode != 0:
        raise RuntimeError(cp.stderr.strip() or cp.stdout.strip() or "git pull failed")
    return cp.stdout.strip()

