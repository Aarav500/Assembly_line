import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
import uuid
import datetime
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from services.github_importer import (
    parse_github_url,
    get_repo_info,
    build_zip_url,
    download_zip_archive,
    extract_zip_safely,
    ensure_dir,
    slugify,
)

load_dotenv()

app = Flask(__name__)

PROJECTS_ROOT = os.getenv("PROJECTS_ROOT", os.path.join(".", "data", "projects"))
MAX_ARCHIVE_SIZE_MB = int(os.getenv("MAX_ARCHIVE_SIZE_MB", "200"))
GITHUB_API_URL = os.getenv("GITHUB_API_URL", "https://api.github.com")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))

ensure_dir(PROJECTS_ROOT)


def redact_token(s: str | None) -> str | None:
    if not s:
        return s
    if len(s) <= 6:
        return "***"
    return s[:3] + "***" + s[-3:]


@app.post("/api/github/import")
def import_github_project():
    try:
        data = request.get_json(force=True, silent=False) or {}
    except Exception:
        return jsonify({"success": False, "error": "Invalid JSON body"}), 400

    raw_url = (data.get("url") or data.get("github_url") or "").strip()
    token = (data.get("token") or "").strip() or None
    ref_override = (data.get("ref") or "").strip() or None
    project_name = (data.get("project_name") or "").strip() or None

    if not raw_url:
        return jsonify({"success": False, "error": "Field 'url' is required"}), 400

    try:
        owner, repo, ref_from_url = parse_github_url(raw_url)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    ref = ref_override or ref_from_url  # may still be None, we'll resolve to default branch later

    # Fetch repo info (default branch, privacy) using API; requires token for private repos
    try:
        repo_info = get_repo_info(owner, repo, token=token, base_api=GITHUB_API_URL, timeout=REQUEST_TIMEOUT)
    except PermissionError as e:
        return jsonify({"success": False, "error": str(e)}), 401
    except FileNotFoundError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to fetch repository info: {e}"}), 502

    default_branch = repo_info.get("default_branch")
    is_private = bool(repo_info.get("private"))

    effective_ref = ref or default_branch or "main"

    zip_url = build_zip_url(owner, repo, effective_ref, base_api=GITHUB_API_URL)

    # Prepare destination path
    display_name = project_name or repo
    slug_base = slugify(display_name)
    project_id = str(uuid.uuid4())
    project_dir = os.path.join(PROJECTS_ROOT, f"{slug_base}-{project_id[:8]}")
    ensure_dir(project_dir)

    # Download and extract
    try:
        archive_path, size_bytes = download_zip_archive(
            zip_url,
            dest_dir=project_dir,
            token=token,
            timeout=REQUEST_TIMEOUT,
            max_size_mb=MAX_ARCHIVE_SIZE_MB,
        )
    except PermissionError as e:
        return jsonify({"success": False, "error": str(e)}), 401
    except FileNotFoundError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 413
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to download archive: {e}"}), 502

    try:
        extracted_root = extract_zip_safely(archive_path, project_dir)
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to extract archive: {e}"}), 500

    # Identify final project path (top-level folder inside extraction)
    # If extracted_root contains a single directory, use it; otherwise use extracted_root itself
    final_path = extracted_root

    # Persist minimal metadata
    meta = {
        "id": project_id,
        "name": display_name,
        "source": "github",
        "url": raw_url,
        "owner": owner,
        "repo": repo,
        "ref": effective_ref,
        "private": is_private,
        "download_size_bytes": size_bytes,
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        "path": os.path.relpath(final_path, PROJECTS_ROOT).replace("\\", "/"),
    }

    try:
        with open(os.path.join(project_dir, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    # Build response (avoid any token leakage)
    response = {
        "success": True,
        "project": meta,
        "warnings": [],
        "debug": {
            "requested_ref": ref_override or ref_from_url,
            "resolved_ref": effective_ref,
            "token_redacted": bool(token),
            "token_preview": redact_token(token) if token else None,
        },
    }
    return jsonify(response), 201


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)



def create_app():
    return app
