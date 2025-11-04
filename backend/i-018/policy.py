import re
from typing import List, Dict
from config import settings


SIGNED_OFF_BY_RE = re.compile(r"^Signed-off-by:\s*(?P<name>.+)\s*<(?P<email>[^>]+)>\s*$", re.IGNORECASE | re.MULTILINE)


def has_dco_signed_off(message: str, author_email: str, committer_email: str) -> bool:
    if not message:
        return False
    matches = SIGNED_OFF_BY_RE.findall(message)
    if not matches:
        return False
    emails = {e.strip().lower() for _, e in matches}
    auth = (author_email or "").strip().lower()
    comm = (committer_email or "").strip().lower()
    if auth in emails or comm in emails:
        return True
    return False


def evaluate_commits_against_policy(commits: List) -> Dict:
    violations = []

    for c in commits:
        commit_violations = []
        # Require signed commits
        if settings.REQUIRE_SIGNED_COMMITS:
            if not c.verified:
                commit_violations.append({"sha": c.sha, "type": "unsigned", "reason": c.verification_reason or "not verified"})
        # Allowed key IDs if configured
        if settings.ALLOWED_SIGNATURE_KEY_IDS:
            if c.verified and (not c.signature_key_id or c.signature_key_id not in settings.ALLOWED_SIGNATURE_KEY_IDS):
                commit_violations.append({"sha": c.sha, "type": "unapproved_key", "key_id": c.signature_key_id})
        # Allowed signers usernames
        if settings.ALLOWED_SIGNER_USERNAMES:
            if c.verified and (not c.signer_username or c.signer_username not in settings.ALLOWED_SIGNER_USERNAMES):
                commit_violations.append({"sha": c.sha, "type": "unapproved_signer", "signer": c.signer_username})
        # Allowed emails - applied to author_email
        if settings.ALLOWED_SIGNER_EMAILS:
            if c.verified and (not c.author_email or c.author_email.lower() not in {e.lower() for e in settings.ALLOWED_SIGNER_EMAILS}):
                commit_violations.append({"sha": c.sha, "type": "unapproved_email", "email": c.author_email})
        # DCO
        if settings.REQUIRE_DCO and not c.dco:
            commit_violations.append({"sha": c.sha, "type": "missing_dco"})

        if commit_violations:
            violations.extend(commit_violations)
            c.policy_passed = False
        else:
            c.policy_passed = True

    policy_passed = len(violations) == 0

    summary = "All commits comply with policy" if policy_passed else f"{len(violations)} policy violation(s) detected"
    return {"policy_passed": policy_passed, "violations": violations, "summary": summary}

