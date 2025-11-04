import os
from typing import List, Optional
import requests
from git import Repo, Actor

class GitClient:
    def ensure_repo(self, path: str) -> Repo:
        return Repo(path)

    def checkout_base(self, repo: Repo, base_branch: str) -> None:
        # Fetch and checkout base
        try:
            repo.git.fetch("--all", "--prune")
        except Exception:
            pass
        try:
            repo.git.checkout(base_branch)
        except Exception:
            # try create or track
            try:
                repo.git.checkout("-b", base_branch, f"origin/{base_branch}")
            except Exception:
                # if still fails, stay on current branch
                pass
        try:
            repo.git.pull("--ff-only")
        except Exception:
            pass

    def create_or_reset_branch(self, repo: Repo, branch_name: str, base_branch: str) -> None:
        # Delete local branch if exists
        if branch_name in repo.branches:
            try:
                repo.git.branch("-D", branch_name)
            except Exception:
                pass
        repo.git.checkout("-b", branch_name, base_branch)

    def add_and_commit(self, repo: Repo, rel_paths: List[str], message: str) -> None:
        if not rel_paths:
            return
        repo.index.add(rel_paths)
        author_name = os.environ.get("GIT_AUTHOR_NAME", "secret-bot")
        author_email = os.environ.get("GIT_AUTHOR_EMAIL", "secret-bot@example.com")
        author = Actor(author_name, author_email)
        repo.index.commit(message, author=author, committer=author)

    def push_branch(self, repo: Repo, branch_name: str, remote_name: str = "origin") -> None:
        remote = repo.remote(remote_name)
        remote.push(refspec=f"HEAD:refs/heads/{branch_name}")

    def create_github_pr(self, owner: str, repo: str, head: str, base: str, title: str, body: str, token: str) -> Optional[str]:
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "secret-remediation-bot"
        }
        payload = {"title": title, "head": head, "base": base, "body": body}
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code in (200, 201):
            data = resp.json()
            return data.get("html_url")
        raise RuntimeError(f"GitHub PR creation failed: {resp.status_code} {resp.text}")

