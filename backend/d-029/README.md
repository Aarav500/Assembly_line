Project: auto-cleanup-of-ephemeral-artifacts-and-preview-resources-af

Description:
A small Flask service that listens to GitHub pull_request closed webhooks and performs cleanup of ephemeral preview resources and artifacts.

Features:
- Verifies GitHub webhook signature (HMAC SHA-256)
- Triggers on pull_request closed events (merged or closed)
- Pluggable cleaners (enable via environment variables):
  - S3 artifacts cleanup (delete keys under a prefix like previews/pr-{pr}/)
  - Kubernetes namespace cleanup (delete namespace like preview-pr-{pr})
  - GitHub Actions artifacts cleanup (delete artifacts matching patterns)
  - GitHub deployments/environment cleanup (set inactive, delete deployments and optionally the environment like pr-{pr})
- Dry-run mode enabled by default for safety

Quickstart:
1) Copy .env.sample to .env and adjust values.
2) Install requirements and run:
   - pip install -r requirements.txt
   - python run.py
3) Configure a GitHub webhook on your repository:
   - Payload URL: http://your-host/webhook
   - Content type: application/json
   - Secret: GITHUB_WEBHOOK_SECRET value
   - Events: Pull requests (or send all events)

Environment variables (key ones):
- DRY_RUN=true|false (default true)
- GITHUB_WEBHOOK_SECRET: required for signature verification
- GITHUB_TOKEN: token with repo scope (for artifacts/deployments cleanup)
- ENABLE_S3_CLEANUP=true|false and S3_BUCKET, S3_PREFIX_TEMPLATE
- ENABLE_K8S_CLEANUP=true|false and K8S_NAMESPACE_TEMPLATE
- ENABLE_GH_ARTIFACTS_CLEANUP=true|false and ARTIFACT_NAME_PATTERNS
- ENABLE_GH_DEPLOYMENTS_CLEANUP=true|false, ENABLE_GH_ENVIRONMENT_DELETE, ENVIRONMENT_NAME_TEMPLATE

Security:
- Do not disable signature verification in production.
- Grant the minimum permissions to GITHUB_TOKEN.

Notes:
- Cleaners are idempotent and skip non-existent resources.
- Adjust templates to match your naming conventions.

