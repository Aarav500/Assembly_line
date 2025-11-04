import os
import shutil
import subprocess
from typing import Dict

class GitOps:
    def __init__(self, repo_dir: str = None):
        self.repo_dir = repo_dir or os.getcwd()

    def _run(self, args, check=True):
        return subprocess.run(args, cwd=self.repo_dir, check=check, capture_output=True, text=True)

    def ensure_repo(self):
        try:
            self._run(["git", "rev-parse", "--is-inside-work-tree"])  # will raise if not a repo
        except Exception:
            raise RuntimeError("Current directory is not a git repository. Initialize a repo and set remotes before running auto-pr.")

    def create_branch(self, branch: str):
        # Create and switch to the branch, if not exists
        self._run(["git", "checkout", "-B", branch])

    def apply_file_change(self, path: str, content: str):
        abspath = os.path.join(self.repo_dir, path)
        os.makedirs(os.path.dirname(abspath), exist_ok=True)
        with open(abspath, "w", encoding="utf-8") as f:
            f.write(content)
        self._run(["git", "add", path])

    def commit_all(self, message: str):
        # Only commit if there is something to commit
        status = self._run(["git", "status", "--porcelain"]).stdout.strip()
        if not status:
            return {"committed": False, "reason": "No changes"}
        self._run(["git", "commit", "-m", message])
        return {"committed": True}

    def push_branch(self, branch: str) -> Dict:
        # Determine remote
        remote = os.getenv("GIT_REMOTE") or self._get_default_remote()
        if not remote:
            return {"pushed": False, "reason": "No git remote configured"}
        # Try pushing
        try:
            self._run(["git", "push", "-u", remote, branch])
            return {"pushed": True, "remote": remote, "branch": branch}
        except subprocess.CalledProcessError as e:
            return {"pushed": False, "reason": e.stderr}

    def _get_default_remote(self):
        try:
            remotes = self._run(["git", "remote"]).stdout.strip().splitlines()
            return remotes[0] if remotes else None
        except Exception:
            return None

