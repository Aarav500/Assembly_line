import json
from datetime import datetime
from typing import Optional
from .github_client import GitHubClient
from .models import Regression, Deployment
from .database import db


class Triager:
    def __init__(self, gh: GitHubClient):
        self.gh = gh

    def _compose_body(self, reg: Regression, dep: Deployment) -> str:
        ts = datetime.utcnow().isoformat() + 'Z'
        direction = "increase" if reg.delta_pct >= 0 else "decrease"
        pct = round(reg.delta_pct * 100.0, 2)
        body = (
            f"Automated regression detected at {ts}.\n\n"
            f"Service: {reg.service}\n"
            f"Env: {reg.env}\n"
            f"Metric: {reg.metric_name}\n"
            f"Deployment: version={dep.version or ''} commit={dep.commit_sha or ''}\n"
            f"Baseline mean: {reg.baseline_mean:.6g}\n"
            f"Post-deploy mean: {reg.post_mean:.6g}\n"
            f"Change: {direction} of {pct}% (z={reg.z_score:.2f})\n\n"
            f"Please investigate. This was detected automatically."
        )
        return body

    def triage(self, reg: Regression, dep: Deployment) -> Optional[str]:
        if not self.gh.enabled():
            return None
        pr_numbers = []
        try:
            if dep.pr_numbers:
                pr_numbers = json.loads(dep.pr_numbers)
        except Exception:
            pr_numbers = []

        body = self._compose_body(reg, dep)
        url = None
        if pr_numbers:
            # Comment on the first PR
            prn = int(pr_numbers[0])
            url = self.gh.comment_on_pr(prn, body)
            reg.assigned_pr = prn
        else:
            title = f"Regression detected: {reg.service}/{reg.env}/{reg.metric_name}"
            url = self.gh.create_issue(title, body, labels=["regression", reg.service, reg.env])
        reg.issue_url = url
        db.session.commit()
        return url

