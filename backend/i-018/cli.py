import argparse
import sys
from db import SessionLocal, init_db
from models import Repository, Commit
from services.github_client import parse_repo_full_name, github_get_pr_commits, github_get_commit
from provenance import extract_commit_record
from policy import evaluate_commits_against_policy


def scan_pr(full_name: str, pr_number: int):
    init_db()
    db = SessionLocal()
    try:
        repo = db.query(Repository).filter_by(full_name=full_name).one_or_none()
        if not repo:
            repo = Repository(full_name=full_name)
            db.add(repo)
            db.commit()
            db.refresh(repo)

        owner, name = parse_repo_full_name(full_name)
        commits_api = github_get_pr_commits(owner, name, pr_number)
        collected = []
        for c in commits_api:
            sha = c.get("sha")
            api_commit = github_get_commit(owner, name, sha)
            record = extract_commit_record(repo_id=repo.id, pr_id=None, commit_payload=c, api_commit=api_commit)
            # Upsert
            cm = db.query(Commit).filter_by(sha=record["sha"], repo_id=repo.id).one_or_none()
            if not cm:
                cm = Commit(**record)
                db.add(cm)
            else:
                for k, v in record.items():
                    setattr(cm, k, v)
            db.commit()
            db.refresh(cm)
            collected.append(cm)

        result = evaluate_commits_against_policy(collected)
        print(result)
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Provenance policy scanner")
    parser.add_argument("repo", help="owner/repo")
    parser.add_argument("pr", type=int, help="Pull request number")
    args = parser.parse_args()
    scan_pr(args.repo, args.pr)

