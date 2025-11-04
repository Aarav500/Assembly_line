Dependabot/Renovate PR Risk Bot (Flask)

Features:
- Listens to GitHub pull_request webhooks
- Detects Dependabot/Renovate PRs
- Analyzes dependency diffs to infer semver change types
- Posts a risk assessment comment and applies labels
- Optional auto-merge when risk and checks pass

Configuration (env vars):
- GITHUB_TOKEN: Personal Access Token for GitHub API (repo scope) if not using GitHub App
- GITHUB_WEBHOOK_SECRET: Secret to validate webhooks
- GITHUB_APP_ID: GitHub App ID (optional)
- GITHUB_APP_PRIVATE_KEY: PEM contents for GitHub App (optional)
- INCLUDE_DRAFTS: true/false to process draft PRs (default false)
- AUTO_MERGE: true/false to enable auto-merge (default false)
- AUTO_MERGE_RISKS: comma list of risk levels allowed to auto-merge (default: low,medium)
- MERGE_METHOD: merge|squash|rebase (default squash)
- AUTOMERGE_LABEL: label added after auto-merge (default automerge)
- BASE_LABELS: comma list base labels to add (default dependencies)
- HIGH_RISK_IF_MANY: mark as high risk if >= this many deps change (default 15)
- MEDIUM_RISK_IF_MANY: mark as medium risk if >= this many deps change (default 7)
- SENSITIVE_PACKAGES: comma list of sensitive packages to escalate (default flask,django,requests,sqlalchemy,openssl,cryptography,gunicorn,fastapi)
- SECURITY_LABELS: labels that imply security updates (unused placeholder)
- MAX_DEPS_IN_COMMENT: limit items in comment (default 50)

Run locally:
- python -m venv .venv && source .venv/bin/activate
- pip install -r requirements.txt
- export FLASK_ENV=development
- export GITHUB_TOKEN=ghp_xxx
- export GITHUB_WEBHOOK_SECRET=yoursecret
- python app.py

Expose webhook publicly via a tunnel (e.g., ngrok) and configure GitHub webhook:
- Payload URL: https://YOUR_URL/webhook
- Content type: application/json
- Secret: GITHUB_WEBHOOK_SECRET
- Events: Pull requests

Notes:
- For GitHub App usage, set GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY and install the app on repos. The server will use the installation token from the webhook payload.
- Auto-merge requires successful checks and a mergeable state.

