Agent Sandbox to Preview Proposed PRs Visually Before Commit

Stack: Python, Flask

Features:
- List GitHub repository PRs and inspect metadata, commits, and changed files
- Visual sandbox preview of PR content: HTML and Markdown rendered safely
- Read-only workspace browser for the checked-out PR head branch
- Rebuild/refresh workspace at any time

Quickstart:
1) Create and activate a virtual environment
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate

2) Install dependencies
   pip install -r requirements.txt

3) (Optional) Set a GitHub token for higher rate limits/private repos
   export GITHUB_TOKEN=ghp_...

4) Run the app
   python run.py

5) Open http://localhost:5000 and enter owner/repo (e.g., octocat/Hello-World)

Notes:
- The workspace clones the PR head repository and checks out the head ref.
- No build steps are executed; previews focus on static HTML/Markdown.
- Previews are served via a sandboxed iframe with CSP for safety.
- Workspaces are stored under ./workspaces by default (override via WORKSPACES_DIR env var).

Security Considerations:
- Preview iframe uses sandbox to isolate content. Scripts are allowed within the sandbox to render static sites but cannot escape the frame.
- Only files within the workspace directory are served; path traversal is prevented.
- Do not deploy this without additional hardening if running in untrusted multi-tenant environments.

