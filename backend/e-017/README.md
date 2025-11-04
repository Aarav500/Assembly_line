Secrets rotation automation and lease-based secrets via Vault

Overview
- Flask service demonstrating:
  - Fetching KV v2 secrets from Vault
  - Generating dynamic, lease-based secrets (e.g., database credentials)
  - Automatic lease renewal in the background
  - Automated rotation for KV secrets (random value) and database root credentials

Endpoints
- GET /healthz | /readyz | /livez | /status: Health checks
- GET /kv/<path>: Read a secret from KV v2. Query params: mount, version
- POST /kv/<path>: Write to KV v2 with body: {"data": { ... }}
- POST /kv/<path>/rotate: Rotate a single field with a new random value. Body: {"field":"password","length":32,"alphabet":"optional","preserve_fields":{}}
- GET /dynamic/<role>?mount=database: Generate dynamic credentials for a DB role; lease added to renewer automatically
- DELETE /leases/<lease_id>: Revoke a tracked lease and stop renewing
- GET /leases: View tracked leases and next renewal times
- POST /rotate/database-root: Rotate DB root for a configured connection: {"mount":"database","connection":"name"}
- GET /scheduler/jobs: List rotation jobs
- POST /scheduler/jobs: Add a rotation job dynamically

Configuration
- See .env.example. Important variables:
  - VAULT_ADDR: Vault URL
  - VAULT_TOKEN: Token (if using token auth)
  - VAULT_AUTH_METHOD: token | kubernetes
  - VAULT_K8S_ROLE, KUBERNETES_JWT_PATH: for Kubernetes auth
  - VAULT_MOUNT_KV: KV v2 mount
  - VAULT_MOUNT_DB: Database engine mount
  - ROTATION_CONFIG_PATH: Path to JSON array of jobs
  - ROTATION_JOBS_JSON: Inline JSON array of jobs

Rotation jobs format
- KV random field rotation
  {
    "type": "kv_random",
    "mount": "secret",
    "path": "app/config",
    "field": "password",
    "length": 32,
    "interval_seconds": 3600
  }
- Database root rotation (requires database engine and connection configured)
  {
    "type": "database_root",
    "mount": "database",
    "connection": "my-postgres",
    "interval_seconds": 86400
  }

Run locally
1) Dev Vault with docker-compose (dev server; not for production):
   docker-compose up -d vault
2) Export environment (optional) and run app:
   export VAULT_ADDR=http://127.0.0.1:8200
   export VAULT_TOKEN=root
   pip install -r requirements.txt
   python app.py
3) In another terminal, test endpoints, e.g.:
   curl http://localhost:8080/healthz

Notes
- The database root rotation endpoint and job require an already-configured database secrets engine and a connection named in Vault.
- Dynamic credentials lease renewal runs in a background thread; it renews leases before expiry and drops leases after repeated failures.
- KV rotation here generates a random value and writes it to KV v2; ensure your Vault policies permit read/write on that path.

Security
- This code is for demonstration. Do not expose it directly to the internet.
- Use TLS for Vault and the app, enforce authentication/authorization, and least-privilege Vault policies.

