import os
import io
import re
import zipfile
import shutil
import tempfile
from urllib.parse import urlparse
from typing import Tuple, Optional

import requests

USER_AGENT = "github-importer/1.0 (+https://github.com)"


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9\-_. ]+", "", value)
    value = re.sub(r"[\s_]+", "-", value)
    value = re.sub(r"-+", "-", value)
    return value.strip("-._") or "project"


class GitHubURLError(ValueError):
    pass


def parse_github_url(url: str) -> Tuple[str, str, Optional[str]]:
    """
    Parse GitHub URL variants into (owner, repo, ref)
    Supports:
    - https://github.com/{owner}/{repo}
    - https://github.com/{owner}/{repo}.git
    - https://github.com/{owner}/{repo}/tree/{branch}
    - git@github.com:{owner}/{repo}.git
    """
    url = url.strip()

    # SSH URL
    ssh_match = re.match(r"^git@github.com:(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)(?:\.git)?$", url)
    if ssh_match:
        owner = ssh_match.group("owner")
        repo = ssh_match.group("repo")
        return owner, repo, None

    # HTTP(S) URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise GitHubURLError(f"Invalid URL: {e}")

    if parsed.netloc.lower() != "github.com":
        raise GitHubURLError("URL must be from github.com")

    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        raise GitHubURLError("URL must be in the form https://github.com/<owner>/<repo>")

    owner = parts[0]
    repo = parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]

    ref = None
    # Handle /tree/<ref>
    if len(parts) >= 4 and parts[2] == "tree":
        ref = parts[3]

    return owner, repo, ref


def _auth_headers(token: Optional[str]) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
    }
    if token:
        # GitHub accepts both 'token' and 'Bearer'; use 'token' for classic and fine-grained
        headers["Authorization"] = f"token {token}"
    return headers


def get_repo_info(owner: str, repo: str, token: Optional[str], base_api: str = "https://api.github.com", timeout: int = 30) -> dict:
    url = f"{base_api.rstrip('/')}/repos/{owner}/{repo}"
    resp = requests.get(url, headers=_auth_headers(token), timeout=timeout)
    if resp.status_code == 404:
        raise FileNotFoundError("Repository not found or access denied")
    if resp.status_code == 401:
        raise PermissionError("Unauthorized: invalid or missing token for private repository")
    if resp.status_code == 403:
        # Could be rate limited or forbidden
        msg = resp.json().get("message", "Forbidden") if resp.headers.get("Content-Type", "").startswith("application/json") else "Forbidden"
        raise PermissionError(f"Forbidden: {msg}")
    resp.raise_for_status()
    return resp.json()


def build_zip_url(owner: str, repo: str, ref: str, base_api: str = "https://api.github.com") -> str:
    return f"{base_api.rstrip('/')}/repos/{owner}/{repo}/zipball/{ref}"


def download_zip_archive(zip_url: str, dest_dir: str, token: Optional[str], timeout: int, max_size_mb: int) -> tuple[str, int]:
    ensure_dir(dest_dir)
    tmp_zip_path = os.path.join(dest_dir, "repo.zip")

    with requests.get(zip_url, headers=_auth_headers(token), stream=True, timeout=timeout) as r:
        if r.status_code == 404:
            raise FileNotFoundError("Archive not found for the specified ref")
        if r.status_code == 401:
            raise PermissionError("Unauthorized: invalid or missing token for private repository")
        if r.status_code == 403:
            raise PermissionError("Forbidden: access denied or rate limited")
        r.raise_for_status()

        content_length = r.headers.get("Content-Length")
        if content_length is not None:
            try:
                length = int(content_length)
                if length > max_size_mb * 1024 * 1024:
                    raise ValueError(f"Archive too large ({length} bytes) > {max_size_mb} MB limit")
            except ValueError:
                # If Content-Length is not an int, ignore and stream with tracking
                pass

        bytes_written = 0
        chunk_size = 1024 * 64
        with open(tmp_zip_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=chunk_size):
                if chunk:
                    bytes_written += len(chunk)
                    if bytes_written > max_size_mb * 1024 * 1024:
                        try:
                            f.close()
                            os.remove(tmp_zip_path)
                        except Exception:
                            pass
                        raise ValueError(f"Archive exceeded {max_size_mb} MB limit during download")
                    f.write(chunk)

    return tmp_zip_path, bytes_written


def _is_within_directory(directory: str, target: str) -> bool:
    abs_directory = os.path.abspath(directory)
    abs_target = os.path.abspath(target)
    return os.path.commonpath([abs_directory]) == os.path.commonpath([abs_directory, abs_target])


def extract_zip_safely(zip_path: str, dest_dir: str) -> str:
    """
    Extract ZIP into dest_dir safely, preventing Zip Slip.
    Returns the path to the extracted root directory.
    """
    if not zipfile.is_zipfile(zip_path):
        raise ValueError("Downloaded file is not a valid ZIP archive")

    # Extract to a temp directory inside dest_dir
    tmp_extract_dir = tempfile.mkdtemp(prefix="extract-", dir=dest_dir)

    with zipfile.ZipFile(zip_path, 'r') as zf:
        for member in zf.infolist():
            member_path = os.path.join(tmp_extract_dir, member.filename)
            if not _is_within_directory(tmp_extract_dir, member_path):
                raise Exception("Unsafe path in archive detected")
        zf.extractall(tmp_extract_dir)

    # Determine top-level folder
    entries = [os.path.join(tmp_extract_dir, e) for e in os.listdir(tmp_extract_dir)]
    top_dirs = [p for p in entries if os.path.isdir(p)]

    if len(top_dirs) == 1 and not [p for p in entries if os.path.isfile(p)]:
        extracted_root = top_dirs[0]
    else:
        extracted_root = tmp_extract_dir

    # Move extracted_root to a stable folder named 'project'
    final_root = os.path.join(dest_dir, "project")
    if os.path.exists(final_root):
        shutil.rmtree(final_root)
    shutil.move(extracted_root, final_root)

    # Cleanup temp extract directory and zip
    try:
        if os.path.isdir(tmp_extract_dir):
            shutil.rmtree(tmp_extract_dir, ignore_errors=True)
        if os.path.isfile(zip_path):
            os.remove(zip_path)
    except Exception:
        pass

    return final_root

