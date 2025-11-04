import os
import shutil
import typing as t
from pathlib import Path
from flask import current_app
from git import Repo, GitCommandError


def workspace_id_for(owner: str, repo: str, pr_number: int) -> str:
    return f"{owner}_{repo}_pr{pr_number}"


def workspace_path(workspace_id: str) -> str:
    return os.path.join(current_app.config["WORKSPACES_DIR"], workspace_id)


def ensure_workspace_for_pr(owner: str, repo: str, pr_number: int, pr: dict) -> str:
    """
    Create or update a local workspace for a PR by cloning the head repo and checking out the head ref.
    Returns the workspace absolute path.
    """
    ws_id = workspace_id_for(owner, repo, pr_number)
    ws_path = workspace_path(ws_id)
    head_repo = pr.get("head", {}).get("repo") or {}
    clone_url = head_repo.get("clone_url")
    head_ref = pr.get("head", {}).get("ref")

    if not clone_url or not head_ref:
        raise RuntimeError("PR head repo or ref not available for workspace creation")

    if not os.path.isdir(ws_path) or not os.listdir(ws_path):
        # Fresh clone
        Repo.clone_from(clone_url, ws_path)
        repo_obj = Repo(ws_path)
        repo_obj.git.checkout(head_ref)
    else:
        # Update existing
        repo_obj = Repo(ws_path)
        try:
            # Ensure origin points to head repo
            origin = repo_obj.remotes.origin
            if origin.url != clone_url:
                origin.set_url(clone_url)
        except Exception:
            # If no origin exists, create it
            repo_obj.create_remote("origin", clone_url)
        # Fetch and checkout ref
        repo_obj.git.fetch("origin", head_ref)
        # Create local branch if it doesn't exist
        local_branches = [h.name for h in repo_obj.heads]
        if head_ref not in local_branches:
            repo_obj.git.checkout("-b", head_ref, f"origin/{head_ref}")
        else:
            repo_obj.git.checkout(head_ref)
            try:
                repo_obj.git.pull("origin", head_ref)
            except GitCommandError:
                # Fallback to hard reset if pull fails
                repo_obj.git.reset("--hard", f"origin/{head_ref}")
    return ws_path


def rebuild_workspace(owner: str, repo: str, pr_number: int, pr: dict) -> str:
    """Force a clean rebuild by removing and re-cloning workspace."""
    ws_id = workspace_id_for(owner, repo, pr_number)
    ws_path = workspace_path(ws_id)
    if os.path.isdir(ws_path):
        shutil.rmtree(ws_path, ignore_errors=True)
    return ensure_workspace_for_pr(owner, repo, pr_number, pr)


def list_directory(workspace_id: str, subpath: str | None = None) -> dict:
    base = Path(workspace_path(workspace_id)).resolve()
    target = (base / (subpath or "")).resolve()
    if base not in target.parents and base != target:
        raise PermissionError("Invalid path")
    entries = []
    for p in sorted(target.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
        entries.append({
            "name": p.name,
            "is_dir": p.is_dir(),
            "size": p.stat().st_size if p.is_file() else None,
            "relpath": str(p.relative_to(base))
        })
    return {"base": str(base), "path": str(target), "entries": entries}


def find_preview_candidates(workspace_id: str, changed_files: list[str] | None = None) -> list[str]:
    base = Path(workspace_path(workspace_id))
    candidates: list[str] = []
    exts = {".html", ".htm", ".md", ".markdown"}
    preferred = ["index.html", "README.md", "readme.md"]

    if changed_files:
        for f in changed_files:
            p = (base / f)
            if p.exists() and p.suffix.lower() in exts:
                candidates.append(str(Path(f)))

    # Always try preferred files at root
    for p in preferred:
        if (base / p).exists() and p not in candidates:
            candidates.insert(0, p)

    # If still empty, search shallowly for html/md
    if not candidates:
        for p in base.rglob("*"):
            if p.is_file() and p.suffix.lower() in exts:
                rel = str(p.relative_to(base))
                if rel not in candidates:
                    candidates.append(rel)
            if len(candidates) >= 50:
                break
    return candidates

