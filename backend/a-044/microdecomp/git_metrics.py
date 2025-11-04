import os
import subprocess
from collections import defaultdict
from typing import Dict, Tuple


def get_git_metrics(repo_path: str) -> Dict:
    repo = os.path.abspath(repo_path)
    if not os.path.isdir(os.path.join(repo, ".git")):
        return {"available": False}
    try:
        cmd = ["git", "-C", repo, "log", "--name-only", "--pretty=format:%H|%ct"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if res.returncode != 0:
            return {"available": False, "error": (res.stderr or res.stdout)}
        cochange = defaultdict(int)
        file_changes = defaultdict(int)
        commit_timestamps = []
        commit_files = []
        for line in res.stdout.splitlines():
            if not line.strip():
                continue
            if "|" in line and len(line.split("|")) == 2 and len(line.split("/")) == 1 and len(line) < 64:
                # new commit header (heuristic)
                if commit_files:
                    for i in range(len(commit_files)):
                        file_changes[commit_files[i]] += 1
                        for j in range(i + 1, len(commit_files)):
                            pair = tuple(sorted((commit_files[i], commit_files[j])))
                            cochange[pair] += 1
                commit_files = []
                _, ts = line.split("|")
                commit_timestamps.append(int(ts))
            else:
                f = line.strip()
                if f and not f.startswith("."):
                    commit_files.append(f)
        # flush last
        if commit_files:
            for i in range(len(commit_files)):
                file_changes[commit_files[i]] += 1
                for j in range(i + 1, len(commit_files)):
                    pair = tuple(sorted((commit_files[i], commit_files[j])))
                    cochange[pair] += 1

        return {
            "available": True,
            "file_changes": dict(file_changes),
            "co_changes": {f"{a}||{b}": c for (a, b), c in cochange.items()},
        }
    except Exception as e:
        return {"available": False, "error": str(e)}

