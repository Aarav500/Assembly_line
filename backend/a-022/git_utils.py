import os
import re
import subprocess
from typing import Dict, Optional


class GitError(Exception):
    def __init__(self, message: str, cmd: Optional[str] = None, stdout: str = "", stderr: str = "", code: Optional[int] = None):
        super().__init__(message)
        self.cmd = cmd
        self.stdout = stdout
        self.stderr = stderr
        self.code = code

    def to_dict(self):
        return {
            "message": str(self),
            "cmd": self.cmd,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "code": self.code,
        }


def run_git(args, repo_path: str) -> subprocess.CompletedProcess:
    cmd = ["git"] + args
    proc = subprocess.run(
        cmd,
        cwd=repo_path,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise GitError(
            f"Git command failed: {' '.join(cmd)}",
            cmd=" ".join(cmd),
            stdout=proc.stdout,
            stderr=proc.stderr,
            code=proc.returncode,
        )
    return proc


def get_current_branch(repo_path: str) -> str:
    # This returns 'HEAD' in detached state; handle gracefully
    out = run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo_path).stdout.strip()
    return out


def get_remotes(repo_path: str) -> Dict[str, Dict[str, str]]:
    out = run_git(["remote", "-v"], repo_path).stdout.strip()
    remotes: Dict[str, Dict[str, str]] = {}
    for line in out.splitlines():
        # e.g. origin  https://github.com/owner/repo.git (fetch)
        #      origin  https://github.com/owner/repo.git (push)
        parts = line.split()
        if len(parts) >= 3:
            name, url, kind = parts[0], parts[1], parts[2].strip("()")
            entry = remotes.setdefault(name, {})
            entry[kind] = url
    return remotes


def branch_exists(repo_path: str, branch: str) -> bool:
    try:
        run_git(["rev-parse", "--verify", branch], repo_path)
        return True
    except GitError:
        return False


def create_branch(repo_path: str, branch: str, base: Optional[str] = None) -> Dict:
    if branch_exists(repo_path, branch):
        # Just checkout existing
        run_git(["checkout", branch], repo_path)
        return {"created": False, "checked_out": True, "branch": branch}
    args = ["checkout", "-b", branch]
    if base:
        # Ensure base exists locally; fetch if needed
        try:
            run_git(["rev-parse", "--verify", base], repo_path)
        except GitError:
            # try fetching from default remote
            run_git(["fetch", "--all", "--prune"], repo_path)
        args.append(base)
    run_git(args, repo_path)
    return {"created": True, "checked_out": True, "branch": branch}


def push_current_branch(repo_path: str, remote: str = "origin") -> Dict:
    branch = get_current_branch(repo_path)
    # Push with upstream
    proc = run_git(["push", "-u", remote, branch], repo_path)
    return {
        "remote": remote,
        "branch": branch,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


REMOTE_SSH_RE = re.compile(r"^(?:ssh://)?git@([^/:]+)[:/](.+?)(?:\.git)?$")
REMOTE_HTTPS_RE = re.compile(r"^https?://([^/]+)/(.+?)(?:\.git)?$")


def parse_remote_url(url: Optional[str]) -> Dict[str, str]:
    if not url:
        raise GitError("Remote URL is empty")
    m = REMOTE_SSH_RE.match(url)
    if not m:
        m = REMOTE_HTTPS_RE.match(url)
    if not m:
        raise GitError(f"Unsupported remote URL format: {url}")
    host = m.group(1)
    path = m.group(2).strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    if "/" not in path:
        raise GitError(f"Cannot parse owner/repo from remote URL: {url}")
    owner, repo = path.split("/", 1)
    return {"host": host, "owner": owner, "repo": repo}

