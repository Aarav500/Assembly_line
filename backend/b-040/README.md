Export to Notion / Google Docs / PDF / Markdown / GitHub Issue

Endpoints:
- POST /export
  JSON body:
  {
    "destination": "notion|google_docs|pdf|markdown|github_issue",
    "title": "My Title",
    "content": "My content...",
    "options": { /* destination-specific options */ }
  }

Destination options:
- notion: { "notion_parent_page_id"?, "notion_database_id"?, "notion_title_property"? }
- google_docs: {}
- github_issue: { "labels"?: ["bug"], "assignees"?: ["octocat"], "github_repo"?: "owner/repo" }
- pdf: { "output_dir"?: "exports" }
- markdown: { "output_dir"?: "exports" }

Setup:
1) Copy .env.example to .env and fill in values.
2) pip install -r requirements.txt
3) python app.py

Notes:
- Google Docs requires a Service Account JSON file and appropriate sharing.
- Notion requires a valid integration token and either NOTION_PARENT_PAGE_ID or NOTION_DATABASE_ID.
- GitHub requires a personal access token with repo scope.

