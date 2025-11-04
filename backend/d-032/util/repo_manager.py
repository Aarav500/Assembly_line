import json
import os
import re
from datetime import datetime
from typing import List, Dict, Optional

try:
    import git  # type: ignore
except Exception:  # pragma: no cover
    git = None


class RepoManager:
    def __init__(self, repo_path: str):
        self.repo_path = os.path.abspath(repo_path)
        self.base_dir = os.path.join(self.repo_path, "canary")
        self.runs_dir = os.path.join(self.base_dir, "runs")
        self.logs_dir = os.path.join(self.base_dir, "logs")
        self._ensure_dirs()
        self._ensure_repo()

    def _ensure_dirs(self):
        os.makedirs(self.runs_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)

    def _ensure_repo(self):
        if git is None:
            return
        if not os.path.isdir(os.path.join(self.repo_path, ".git")):
            repo = git.Repo.init(self.repo_path)
            with repo.config_writer() as cw:
                try:
                    cw.set_value("user", "name", cw.get_value("user", "name"))
                except Exception:
                    cw.set_value("user", "name", "canary-bot")
                try:
                    cw.set_value("user", "email", cw.get_value("user", "email"))
                except Exception:
                    cw.set_value("user", "email", "canary-bot@example.com")
        else:
            # open repo to ensure valid
            git.Repo(self.repo_path)

    def sanitize_id(self, s: str) -> str:
        s = s.strip().lower()
        s = re.sub(r"[^a-z0-9._-]", "-", s)
        return s

    def save_run(self, run: Dict, commit_message: Optional[str] = None):
        run_id = self.sanitize_id(run.get("id") or "")
        if not run_id:
            raise ValueError("Run must have an id")
        path = os.path.join(self.runs_dir, f"{run_id}.json")
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(run, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp_path, path)
        self._git_add_commit([path], commit_message or f"Save run {run_id}")

    def append_log(self, run_id: str, entry: Dict, commit_message: Optional[str] = None):
        run_id = self.sanitize_id(run_id)
        path = os.path.join(self.logs_dir, f"{run_id}.log")
        line = self._format_log_entry(entry)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        self._git_add_commit([path], commit_message or f"Append decision log {run_id}")

    def _format_log_entry(self, entry: Dict) -> str:
        ts = entry.get("timestamp") or datetime.utcnow().isoformat()
        user = entry.get("user", "unknown")
        result = entry.get("result", "")
        reason = entry.get("reason", "").replace("\n", " ")
        meta = entry.get("metadata")
        meta_str = f" | meta={json.dumps(meta, sort_keys=True)}" if meta else ""
        return f"[{ts}] user={user} result={result} reason={reason}{meta_str}"

    def list_runs(self) -> List[Dict]:
        runs: List[Dict] = []
        for name in sorted(os.listdir(self.runs_dir)):
            if not name.endswith('.json'):
                continue
            path = os.path.join(self.runs_dir, name)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    runs.append(json.load(f))
            except Exception:
                continue
        return runs

    def get_run(self, run_id: str) -> Optional[Dict]:
        run_id = self.sanitize_id(run_id)
        path = os.path.join(self.runs_dir, f"{run_id}.json")
        if not os.path.isfile(path):
            return None
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def list_logs(self) -> List[Dict]:
        items = []
        for name in sorted(os.listdir(self.logs_dir)):
            if not name.endswith('.log'):
                continue
            path = os.path.join(self.logs_dir, name)
            try:
                st = os.stat(path)
                items.append({
                    "run_id": name[:-4],
                    "filename": name,
                    "size": st.st_size,
                    "modified": datetime.utcfromtimestamp(st.st_mtime).isoformat() + "Z",
                })
            except Exception:
                continue
        return items

    def get_log_lines(self, run_id: str, max_lines: int = 500) -> List[str]:
        run_id = self.sanitize_id(run_id)
        path = os.path.join(self.logs_dir, f"{run_id}.log")
        if not os.path.isfile(path):
            return []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()[-max_lines:]
            return [line.rstrip('\n') for line in lines]
        except Exception:
            return []

    def _git_add_commit(self, paths: List[str], message: str):
        if git is None:
            return
        try:
            repo = git.Repo(self.repo_path)
            # Convert to repo-relative paths
            rel_paths = [os.path.relpath(p, self.repo_path) for p in paths]
            repo.index.add(rel_paths)
            if repo.is_dirty(index=True, working_tree=True, untracked_files=True):
                repo.index.commit(message)
        except Exception:
            # Non-fatal if git fails
            pass

