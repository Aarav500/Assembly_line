import os
import mimetypes
from pathlib import Path
from urllib.parse import quote
from flask import Blueprint, current_app, render_template, request, redirect, url_for, abort, jsonify, Response, send_file
import markdown2

from .services.github_client import get_client
from .services.repo_manager import (
    workspace_id_for,
    ensure_workspace_for_pr,
    rebuild_workspace,
    list_directory,
    find_preview_candidates,
    workspace_path,
)

bp = Blueprint("main", __name__)


def parse_repo_full_name(repo_input: str) -> tuple[str, str]:
    value = repo_input.strip().strip("/")
    if value.startswith("https://github.com/"):
        value = value.split("https://github.com/")[-1]
    parts = value.split("/")
    if len(parts) != 2:
        raise ValueError("Repository must be in 'owner/repo' format")
    return parts[0], parts[1]


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/repo", methods=["POST"]) 
def go_repo():
    repo_input = request.form.get("repo")
    try:
        owner, repo = parse_repo_full_name(repo_input)
    except Exception as e:
        return render_template("index.html", error=str(e), last=repo_input or "")
    return redirect(url_for("main.repo", owner=owner, repo=repo))


@bp.route("/repo/<owner>/<repo>")
def repo(owner: str, repo: str):
    gh = get_client()
    try:
        repo_info = gh.get_repo(owner, repo)
        prs = gh.list_pull_requests(owner, repo, state=request.args.get("state", "open"))
    except Exception as e:
        return render_template("repo.html", owner=owner, repo=repo, error=str(e), prs=[], repo_info=None)
    return render_template("repo.html", owner=owner, repo=repo, prs=prs, repo_info=repo_info)


@bp.route("/repo/<owner>/<repo>/pr/<int:number>")
def pr_view(owner: str, repo: str, number: int):
    gh = get_client()
    try:
        pr = gh.get_pull_request(owner, repo, number)
        files = gh.get_pull_request_files(owner, repo, number)
        commits = gh.get_pull_request_commits(owner, repo, number)
    except Exception as e:
        return render_template("pr.html", owner=owner, repo=repo, number=number, error=str(e))

    try:
        ws_path = ensure_workspace_for_pr(owner, repo, number, pr)
    except Exception as e:
        ws_path = None
        ws_error = str(e)
    else:
        ws_error = None

    ws_id = workspace_id_for(owner, repo, number)
    changed_files = [f.get("filename") for f in files]
    preview_candidates = find_preview_candidates(ws_id, changed_files=changed_files)

    selected_preview = request.args.get("file") or (preview_candidates[0] if preview_candidates else None)

    return render_template(
        "pr.html",
        owner=owner,
        repo=repo,
        number=number,
        pr=pr,
        files=files,
        commits=commits,
        ws_id=ws_id,
        ws_path=ws_path,
        ws_error=ws_error,
        preview_candidates=preview_candidates,
        selected_preview=selected_preview,
    )


@bp.route("/api/rebuild/<owner>/<repo>/<int:number>", methods=["POST"]) 
def api_rebuild(owner: str, repo: str, number: int):
    gh = get_client()
    try:
        pr = gh.get_pull_request(owner, repo, number)
        rebuild_workspace(owner, repo, number, pr)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/api/list/<ws_id>")
def api_list_dir(ws_id: str):
    sub = request.args.get("path")
    try:
        data = list_directory(ws_id, subpath=sub)
        return jsonify({"ok": True, **data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


def _safe_ws_file_path(ws_id: str, filename: str | None) -> Path:
    base = Path(workspace_path(ws_id)).resolve()
    if filename:
        target = (base / filename).resolve()
    else:
        target = base
    if base not in target.parents and base != target:
        abort(403)
    return target


@bp.route("/preview/<ws_id>/")
@bp.route("/preview/<ws_id>/<path:filename>")
def preview(ws_id: str, filename: str | None = None):
    base = Path(workspace_path(ws_id)).resolve()
    target = _safe_ws_file_path(ws_id, filename)

    if target.is_dir():
        # Try to serve index.html in this directory
        index_file = target / "index.html"
        if index_file.exists():
            target = index_file
        else:
            # Try README
            for md in (target / "README.md", target / "readme.md"):
                if md.exists():
                    target = md
                    break

    if not target.exists() or not target.is_file():
        abort(404)

    # Render markdown to HTML with basic template wrapper
    if target.suffix.lower() in {".md", ".markdown"}:
        with open(target, "r", encoding="utf-8", errors="ignore") as f:
            html = markdown2.markdown(f.read(), extras=["fenced-code-blocks", "tables", "strike", "task_list"])
        content = f"""
<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{target.name}</title>
  <link rel=\"stylesheet\" href=\"/static/css/styles.css\" />
</head>
<body class=\"markdown-body\">
<div class=\"container\">{html}</div>
</body>
</html>
"""
        return Response(content, mimetype="text/html")

    # Otherwise, serve as static file
    mime, _ = mimetypes.guess_type(str(target))
    mime = mime or "application/octet-stream"
    return send_file(str(target), mimetype=mime, as_attachment=False, download_name=target.name)


@bp.app_template_filter("filesize")
def filesize(num):
    try:
        num = int(num)
    except Exception:
        return "-"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < 1024.0:
            return f"{num:3.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} PB"


@bp.app_template_filter("basename")
def basename(p: str):
    return os.path.basename(p)

