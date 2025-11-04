Visual Diff Viewer for AI-generated PRs and Auto-applied Patches

Stack: Python, Flask.

Quickstart:
- python3 -m venv .venv && source .venv/bin/activate
- pip install -r requirements.txt
- python app.py
- Open http://localhost:5000

Features:
- Upload unified diff/patch files or paste diff text
- Fetch GitHub PR diff by owner/repo/PR number (optional token)
- View local applied patches from applied_patches/ directory
- Side-by-side visual diff with per-file and total stats

Environment:
- APPLIED_PATCHES_DIR: directory to scan for .patch/.diff files (default: applied_patches)

Security notes:
- Tokens are used only for API calls and not stored persistently.

