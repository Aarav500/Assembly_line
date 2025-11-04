suggest-immediate-minimal-viable-fixes-one-line-suggestions-

Description: Suggest immediate minimal viable fixes (one-line suggestions) and create PRs

Stack: python, flask

Quickstart:
- pip install -r requirements.txt
- cp .env.example .env and set GITHUB_TOKEN
- python app.py

Endpoints:
- GET /health
- POST /suggest
  body: { "error_message"?: str, "code"?: str, "diff"?: str, "text"?: str }
  returns: { "suggestions": [str] }

- POST /create_pr
  body: {
    "repo_owner": str,
    "repo_name": str,
    "base_branch"?: str = "main",
    "target_file_path": str,
    "new_content"?: str,          # optional direct content
    "search"?: str,               # used if new_content not provided
    "replace"?: str,              # used if new_content not provided
    "commit_message"?: str,
    "pr_title"?: str,
    "pr_body"?: str,
    "branch_name"?: str
  }
  returns: { "branch": str, "commit_message": str, "pull_request": { "number": int, "url": str, ... } }

Auth:
- Provide GITHUB_TOKEN in environment or send header: Authorization: token <TOKEN> or bearer <TOKEN>

Notes:
- create_pr uses a simple single replacement (first occurrence). If search is not found, it returns an error.
- If the target file does not exist on base branch, provide new_content to create it.

