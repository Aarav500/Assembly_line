import os
from typing import List


class Config:
    def __init__(self):
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.github_webhook_secret = os.getenv("GITHUB_WEBHOOK_SECRET")
        # GitHub App (optional)
        self.github_app_id = os.getenv("GITHUB_APP_ID")
        self.github_app_private_key = os.getenv("GITHUB_APP_PRIVATE_KEY")

        # Behavior flags
        self.include_drafts = os.getenv("INCLUDE_DRAFTS", "false").lower() == "true"
        self.auto_merge = os.getenv("AUTO_MERGE", "false").lower() == "true"
        self.auto_merge_risk_levels: List[str] = (os.getenv("AUTO_MERGE_RISKS", "low,medium").replace(" ", "").split(","))
        self.merge_method = os.getenv("MERGE_METHOD", "squash")  # merge|squash|rebase
        self.automerge_label = os.getenv("AUTOMERGE_LABEL", "automerge")

        # Commenting / labeling
        base_labels = os.getenv("BASE_LABELS", "dependencies").strip()
        self.base_labels = [l for l in base_labels.split(",") if l]

        # Risk policy tuning
        self.high_risk_major_bump = os.getenv("HIGH_RISK_MAJOR_BUMP", "true").lower() == "true"
        self.medium_risk_minor_bump = os.getenv("MEDIUM_RISK_MINOR_BUMP", "true").lower() == "true"
        self.low_risk_patch_bump = os.getenv("LOW_RISK_PATCH_BUMP", "true").lower() == "true"
        self.high_risk_if_many = int(os.getenv("HIGH_RISK_IF_MANY", "15"))
        self.medium_risk_if_many = int(os.getenv("MEDIUM_RISK_IF_MANY", "7"))
        self.sensitive_packages = [p.strip() for p in os.getenv(
            "SENSITIVE_PACKAGES",
            "flask,django,requests,sqlalchemy,openssl,cryptography,gunicorn,fastapi"
        ).split(",") if p.strip()]

        # Security labels to detect security updates
        self.security_labels = [l.strip() for l in os.getenv("SECURITY_LABELS", "security,dependencies-security").split(",") if l.strip()]

        # Comment verbosity
        self.max_dependencies_in_comment = int(os.getenv("MAX_DEPS_IN_COMMENT", "50"))

