import hashlib
import hmac
import requests
from typing import Optional, Tuple, List, Dict
from config import settings


API_BASE = "https://api.github.com"


def verify_github_webhook_signature(secret: str, payload: bytes, signature_header: Optional[str]) -> bool:
    if not signature_header:
        return False
    try:
        sha_name, signature = signature_header.split("=", 1)
    except ValueError:
        return False
    if sha_name != "sha256":
        return False
    mac = hmac.new(secret.encode("utf-8"), msg=payload, digestmod=hashlib.sha256)
    expected = mac.hexdigest()
    # Use hmac.compare_digest to avoid timing attacks
    return hmac.compare_digest(expected, signature)


def parse_repo_full_name(full_name: str) -> Tuple[str, str]:
    owner, name = full_name.split("/", 1)
    return owner, name


def _headers() -> Dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    if settings.GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN}"
    return headers


def github_get_commit(owner: str, repo: str, sha: str) -> Optional[Dict]:
    url = f"{API_BASE}/repos/{owner}/{repo}/commits/{sha}"
    r = requests.get(url, headers=_headers(), timeout=20)
    if r.status_code == 200:
        return r.json()
    return None


def github_get_pr_commits(owner: str, repo: str, number: int) -> List[Dict]:
    results = []
    page = 1
    while True:
        url = f"{API_BASE}/repos/{owner}/{repo}/pulls/{number}/commits?page={page}&per_page=100"
        r = requests.get(url, headers=_headers(), timeout=20)
        if r.status_code != 200:
            break
        batch = r.json()
        if not batch:
            break
        results.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return results


def github_set_commit_status(owner: str, repo: str, sha: str, state: str, context: str, description: Optional[str] = None, target_url: Optional[str] = None) -> None:
    # state: error, failure, pending, success
    url = f"{API_BASE}/repos/{owner}/{repo}/statuses/{sha}"
    payload = {
        "state": state,
        "context": context,
    }
    if description:
        payload["description"] = description
    if target_url:
        payload["target_url"] = target_url
    requests.post(url, json=payload, headers=_headers(), timeout=20)

