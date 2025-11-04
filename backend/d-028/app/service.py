import logging
from typing import Dict, List, Optional
from flask import current_app
from .github_client import GitHubClient
from .parsers import extract_repro, build_issue_body, build_pr_body, make_r_repro_script, make_text_repro_notes


def _repo_allowed(payload: Dict) -> bool:
    repo = payload.get("repository", {})
    full_name = repo.get("full_name")
    private = repo.get("private", False)
    return current_app.config_obj.repo_allowed(full_name, private) if hasattr(current_app, 'config_obj') else current_app.config.get('ALLOW_PRIVATE_REPOS', True)


def _get_repo_info(payload: Dict):
    repo = payload.get("repository", {})
    owner = repo.get("owner", {}).get("login")
    repo_name = repo.get("name")
    full_name = repo.get("full_name")
    default_branch = repo.get("default_branch", "main")
    private = repo.get("private", False)
    return owner, repo_name, full_name, default_branch, private


def _collect_failed_jobs_and_logs(gh: GitHubClient, owner: str, repo: str, run_id: int, max_bytes: int):
    failed_jobs = []
    logs_text = ""
    try:
        jobs = gh.get_workflow_jobs(owner, repo, run_id)
        for job in jobs.get("jobs", []):
            if job.get("conclusion") == "failure":
                failed_jobs.append(job.get("name") or f"job-{job.get('id')}")
                try:
                    logs_text += f"\n\n===== Logs for job: {job.get('name')} =====\n"
                    logs_text += gh.get_job_logs_text(owner, repo, job.get("id"), max_bytes)
                except Exception as e:
                    logging.warning("Unable to fetch logs for job %s: %s", job.get("id"), e)
    except Exception as e:
        logging.warning("Unable to fetch workflow jobs: %s", e)
    return failed_jobs, logs_text


def process_github_event(payload: Dict, event: str) -> Dict:
    if event not in ("workflow_run", "check_suite", "check_run"):
        return {"skipped": True, "reason": f"Unsupported event {event}"}

    owner, repo, full_name, default_branch, private = _get_repo_info(payload)

    if not current_app.config.get("GITHUB_TOKEN"):
        raise RuntimeError("GITHUB_TOKEN is not configured")

    if not current_app.config.get("ALLOW_PRIVATE_REPOS", True) and private:
        return {"skipped": True, "reason": "Private repo not allowed"}

    if current_app.config.get("REPO_ALLOWLIST"):
        if full_name not in current_app.config.get("REPO_ALLOWLIST"):
            return {"skipped": True, "reason": f"Repo {full_name} not in allowlist"}

    run = None
    head_sha = None
    run_html_url = None
    run_id = None

    if event == "workflow_run":
        action = payload.get("action")
        run = payload.get("workflow_run", {})
        conclusion = run.get("conclusion")
        if action != "completed" or conclusion != "failure":
            return {"skipped": True, "reason": f"workflow_run action={action} conclusion={conclusion}"}
        head_sha = run.get("head_sha")
        run_html_url = run.get("html_url")
        run_id = run.get("id")
    elif event == "check_suite":
        action = payload.get("action")
        suite = payload.get("check_suite", {})
        conclusion = suite.get("conclusion")
        if action != "completed" or conclusion != "failure":
            return {"skipped": True, "reason": f"check_suite action={action} conclusion={conclusion}"}
        head_sha = suite.get("head_sha")
        run_html_url = suite.get("url")
        run_id = suite.get("id")
    elif event == "check_run":
        action = payload.get("action")
        check_run = payload.get("check_run", {})
        conclusion = check_run.get("conclusion")
        if action != "completed" or conclusion != "failure":
            return {"skipped": True, "reason": f"check_run action={action} conclusion={conclusion}"}
        head_sha = check_run.get("head_sha")
        run_html_url = check_run.get("html_url")
        run_id = check_run.get("check_suite", {}).get("id") or check_run.get("id")

    gh = GitHubClient()

    # Try collect failed jobs and logs for repro
    max_bytes = int(current_app.config.get("MAX_LOG_BYTES", 4 * 1024 * 1024))
    failed_jobs, logs_text = _collect_failed_jobs_and_logs(gh, owner, repo, run_id, max_bytes)

    repro = extract_repro(logs_text or "")

    labels = current_app.config.get("DEFAULT_LABELS", [])
    assignees = current_app.config.get("DEFAULT_ASSIGNEES", [])

    issue_url = None
    pr_url = None

    if current_app.config.get("ENABLE_ISSUE_CREATION", True):
        title = f"CI failure: {full_name} run {run_id} @ {head_sha[:7]}"
        issue_body = build_issue_body(full_name, run_html_url or "", run_id, head_sha or "", repro, failed_jobs)
        issue = gh.create_issue(owner, repo, title, issue_body, labels, assignees)
        issue_url = issue.get("html_url")

    if current_app.config.get("ENABLE_PR_CREATION", True):
        base_branch = default_branch
        branch_name = f"{current_app.config.get('PR_BRANCH_PREFIX', 'ci-repro/run-')}{run_id}"
        try:
            base_sha = gh.get_branch_sha(owner, repo, base_branch)
            gh.create_branch(owner, repo, branch_name, base_sha)

            author = {
                "name": current_app.config.get("CONTENT_COMMIT_AUTHOR_NAME", "ci-repro-bot"),
                "email": current_app.config.get("CONTENT_COMMIT_AUTHOR_EMAIL", "ci-repro-bot@example.com"),
            }

            # Write reproduction artifacts
            r_script_path = f"repro/run_{run_id}_repro.R"
            notes_path = f"repro/run_{run_id}_notes.txt"
            r_script_content = make_r_repro_script(repro, run_id, head_sha or "")
            notes_content = make_text_repro_notes(repro, run_id, head_sha or "")

            gh.create_or_update_file(owner, repo, r_script_path, r_script_content.encode("utf-8"), f"chore(repro): add R repro script for failed run {run_id}", branch_name, author)
            gh.create_or_update_file(owner, repo, notes_path, notes_content.encode("utf-8"), f"docs(repro): add repro notes for failed run {run_id}", branch_name, author)

            pr_title = f"Repro: CI failed run {run_id}"
            pr_body = build_pr_body(full_name, run_html_url or "", run_id, head_sha or "", repro)
            pr = gh.create_pr(owner, repo, branch_name, base_branch, pr_title, pr_body, draft=current_app.config.get("PR_DRAFT", True))
            pr_url = pr.get("html_url") or pr.get("message")
        except Exception as e:
            logging.exception("Failed to create PR for repro: %s", e)

    return {
        "ok": True,
        "issue_url": issue_url,
        "pr_url": pr_url,
        "failed_jobs": failed_jobs,
    }

