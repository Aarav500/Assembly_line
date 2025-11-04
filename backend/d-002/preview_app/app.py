import os
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PR Preview {{ pr_number or '' }}</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; padding: 2rem; line-height: 1.5; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
    .card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 1rem; }
    code { background: #f3f4f6; padding: 0.2rem 0.4rem; border-radius: 4px; }
  </style>
</head>
<body>
  <h1>PR Preview Environment</h1>
  <p>This is an ephemeral environment for previewing changes from a Pull Request.</p>

  <div class="grid">
    <div class="card">
      <h3>PR Metadata</h3>
      <ul>
        <li><strong>PR Number:</strong> <code>{{ pr_number }}</code></li>
        <li><strong>PR Title:</strong> {{ pr_title }}</li>
        <li><strong>Head:</strong> <code>{{ pr_head }}</code></li>
        <li><strong>Base:</strong> <code>{{ pr_base }}</code></li>
        <li><strong>SHA:</strong> <code>{{ pr_sha }}</code></li>
        <li><strong>Repository:</strong> {{ repo_full_name }}</li>
        <li><strong>URL:</strong> <a href="{{ pr_html_url }}" target="_blank" rel="noopener">{{ pr_html_url }}</a></li>
      </ul>
    </div>
    <div class="card">
      <h3>Runtime</h3>
      <ul>
        <li><strong>App:</strong> Flask</li>
        <li><strong>Process:</strong> Gunicorn</li>
        <li><strong>Container Port:</strong> 8000</li>
        <li><strong>ENV:</strong> {{ flask_env }}</li>
      </ul>
    </div>
  </div>

  <div class="card" style="margin-top: 1rem;">
    <h3>Environment Variables</h3>
    <pre>{{ env_dump }}</pre>
  </div>
</body>
</html>
"""

@app.route("/")
def index():
    pr_number = os.getenv("PR_NUMBER", "")
    pr_title = os.getenv("PR_TITLE", "")
    pr_head = os.getenv("PR_HEAD", "")
    pr_base = os.getenv("PR_BASE", "")
    pr_sha = os.getenv("PR_SHA", "")
    pr_html_url = os.getenv("PR_HTML_URL", "")
    repo_full_name = os.getenv("REPO_FULL_NAME", "")

    env_dump = "\n".join(
        f"{k}={v}" for k, v in sorted(os.environ.items())
        if k.startswith("PR_") or k in {"REPO_FULL_NAME", "FLASK_ENV"}
    )

    return render_template_string(
        TEMPLATE,
        pr_number=pr_number,
        pr_title=pr_title,
        pr_head=pr_head,
        pr_base=pr_base,
        pr_sha=pr_sha,
        pr_html_url=pr_html_url,
        repo_full_name=repo_full_name,
        flask_env=os.getenv("FLASK_ENV", "production"),
        env_dump=env_dump,
    )

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)

