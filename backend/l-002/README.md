Centralized secrets store integration with fine-grained access control

Overview
- Flask API exposing a secrets service with pluggable centralized secrets providers (in-memory or HashiCorp Vault KV v2)
- Fine-grained, path-based access control enforced by a policy engine using roles and allow/deny rules with glob patterns
- Simple API key authentication via X-API-Key header
- JSON audit logs to stdout for read/write/delete actions

Endpoints
- GET /health
- GET /me
- GET /secrets?prefix=...
- GET /secrets/<path>
- PUT /secrets/<path> {"value": any}
- DELETE /secrets/<path>

Quickstart (memory provider)
1) python -m venv .venv && source .venv/bin/activate
2) pip install -r requirements.txt
3) export SECRETS_PROVIDER=memory
4) python app.py
5) curl -H "X-API-Key: alice-key-123" http://localhost:5000/secrets/app/dev/db_password

Vault provider
- Prereqs: a running Vault with KV v2 enabled at mount (default: secret)
- Env vars:
  - SECRETS_PROVIDER=vault
  - VAULT_ADDR, VAULT_TOKEN, VAULT_KV_MOUNT (optional, default secret), VAULT_NAMESPACE (optional)

Policies
- policies.yaml defines users and role-based rules
- Globs supported in path (e.g., app/dev/**)
- Deny rules take precedence over allows

Notes
- In-memory provider flattens nested YAML keys into path strings separated by '/'
- Ensure you protect policies.yaml and environment variables in production

