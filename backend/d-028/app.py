import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
import os
import requests
from datetime import datetime

app = Flask(__name__)

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
GITHUB_REPO = os.environ.get('GITHUB_REPO', '')

@app.route('/')
def index():
    return jsonify({'status': 'ok', 'message': 'CI Auto-Issue Creator'})

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})

@app.route('/webhook/ci-failure', methods=['POST'])
def ci_failure_webhook():
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    build_id = data.get('build_id', 'unknown')
    job_name = data.get('job_name', 'unknown')
    error_log = data.get('error_log', '')
    branch = data.get('branch', 'main')
    commit_sha = data.get('commit_sha', '')
    
    issue_title = f"CI Failure: {job_name} (Build #{build_id})"
    issue_body = generate_issue_body(job_name, build_id, error_log, branch, commit_sha)
    
    if GITHUB_TOKEN and GITHUB_REPO:
        issue_result = create_github_issue(issue_title, issue_body)
        
        if issue_result.get('number'):
            pr_result = create_github_pr(issue_result['number'], job_name, branch, commit_sha)
            return jsonify({
                'status': 'success',
                'issue': issue_result,
                'pr': pr_result
            })
        
        return jsonify({'status': 'success', 'issue': issue_result})
    
    return jsonify({
        'status': 'simulated',
        'message': 'Would create issue and PR',
        'issue_title': issue_title,
        'issue_body': issue_body
    })

def generate_issue_body(job_name, build_id, error_log, branch, commit_sha):
    body = f"""## CI Build Failure Report

**Job Name:** {job_name}
**Build ID:** {build_id}
**Branch:** {branch}
**Commit:** {commit_sha}
**Timestamp:** {datetime.utcnow().isoformat()}

### Error Log
```
{error_log[:1000]}
```

### Reproduction Steps
1. Checkout branch `{branch}` at commit `{commit_sha}`
2. Run the failing test suite: `pytest`
3. Review the error output above

### Expected Behavior
All CI tests should pass successfully.

### Actual Behavior
CI job `{job_name}` failed with the error log shown above.

---
*This issue was automatically created from a CI failure.*
"""
    return body

def create_github_issue(title, body):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/issues"
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    payload = {
        'title': title,
        'body': body,
        'labels': ['ci-failure', 'auto-generated']
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {'error': str(e)}

def create_github_pr(issue_number, job_name, branch, commit_sha):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/pulls"
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    pr_branch = f"fix/ci-failure-{issue_number}"
    pr_title = f"Fix CI failure in {job_name} (closes #{issue_number})"
    pr_body = f"""## Fix for CI Failure

This PR addresses the CI failure reported in #{issue_number}.

### Changes
- [ ] Fix for {job_name}
- [ ] Add reproduction test
- [ ] Verify CI passes

### Related Issue
Closes #{issue_number}

---
*This PR was automatically created from a CI failure.*
"""
    
    payload = {
        'title': pr_title,
        'body': pr_body,
        'head': pr_branch,
        'base': branch
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 422:
            return {'error': 'Branch does not exist or PR already exists'}
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {'error': str(e)}

if __name__ == '__main__':
    app.run(debug=True, port=5000)



def create_app():
    return app


@app.route('/healthz', methods=['GET'])
def _auto_stub_healthz():
    return 'Auto-generated stub for /healthz', 200
