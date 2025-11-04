import os
import requests
from typing import Dict, Any


def export_to_github_issue(title: str, content: str, options: Dict[str, Any], settings) -> Dict[str, Any]:
    token = settings.GITHUB_TOKEN
    repo = options.get('github_repo') or settings.GITHUB_REPO
    labels = options.get('labels')  # list of strings
    assignees = options.get('assignees')  # list of strings

    if not token:
        raise ValueError("GITHUB_TOKEN is not configured")
    if not repo or '/' not in repo:
        raise ValueError("GITHUB_REPO must be in the form 'owner/repo'")

    url = f"https://api.github.com/repos/{repo}/issues"
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json'
    }
    body = {
        'title': title or 'Untitled',
        'body': content or ''
    }
    if isinstance(labels, list):
        body['labels'] = labels
    if isinstance(assignees, list):
        body['assignees'] = assignees

    resp = requests.post(url, headers=headers, json=body, timeout=30)
    if resp.status_code >= 400:
        raise RuntimeError(f"GitHub API error {resp.status_code}: {resp.text}")

    data = resp.json()
    return {
        'number': data.get('number'),
        'url': data.get('html_url')
    }

