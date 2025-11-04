Repo-folder sync watcher (auto-detect file changes)

A lightweight Flask service that watches one or more local Git repositories for file changes and automatically commits and optionally pushes them to a remote. Uses watchdog for file change detection and git CLI.

Features
- Watch multiple directories (each must be or can be initialized as a git repo)
- Debounced auto-commit and optional auto-push
- REST API to manage watchers, force sync, and pull from remote
- Environment variable bootstrapping (WATCH_PATHS)

Quick start
1) Install dependencies:
   pip install -r requirements.txt

2) Export optional environment variables:
   export WATCH_PATHS="/path/to/repo1,/path/to/repo2"
   export GIT_AUTHOR_NAME="Auto Sync Bot"
   export GIT_AUTHOR_EMAIL="autosync@example.com"
   export GIT_REMOTE="origin"            # default remote name
   export GIT_BRANCH="main"               # default branch
   export DEBOUNCE_SECONDS=2.0
   export AUTO_PUSH=true
   export AUTO_INIT=false                 # set true to auto git init directories
   export GIT_REMOTE_URL="git@github.com:user/repo.git"  # optional, used if remote is missing

3) Run the server:
   python app.py

API
- GET /health
- GET /watchers
- POST /watchers
  Body JSON: {"path": "/abs/path", "debounce_seconds": 2.0, "remote": "origin", "branch": "main", "auto_push": true, "auto_init": false}
- GET /watchers/<id>
- DELETE /watchers/<id>
- POST /watchers/<id>/sync
- POST /watchers/<id>/pull
- POST /watchers/<id>/pause
- POST /watchers/<id>/resume

Notes
- Ensure git is installed and available in PATH.
- When auto-push is enabled, make sure credentials are configured (e.g., SSH agent or Git credential helper).
- The watcher ignores the .git directory itself but includes dotfiles in the repo root by default.
- Commits are created only if there are staged changes. Debounce reduces redundant commits on bursty file events.

