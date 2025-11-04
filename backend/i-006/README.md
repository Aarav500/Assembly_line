BYOK and KMS integration with role-scoped access and audits

Overview
- Flask API demonstrating Bring Your Own Key (BYOK) workflows with envelope encryption using either AWS KMS or a local KMS fallback.
- Role-scoped access control (admin, user, auditor) via headers.
- Comprehensive auditing persisted to SQLite and audit.log.

Quick start
1) Python environment
   - Python 3.11+
   - pip install -r requirements.txt

2) Configuration
   - Default DB: sqlite:///app.db
   - Local KMS fallback will create local_kms_master.key in project dir
   - To use AWS KMS, export AWS credentials and AWS_KMS_KEY_ID

3) Run
   - python app.py

Headers for auth/tenancy
- X-User-Id: user identifier (string)
- X-User-Role: admin|user|auditor
- X-Tenant-Id: required for role=user

Endpoints
- GET /health
- POST /keys/import (admin)
  body: { name, tenant_id, key_material_b64 }
- POST /keys/generate (admin)
  body: { name, tenant_id, size? 16|24|32 }
- GET /keys (admin|user|auditor)
  query: tenant_id?
- GET /keys/{id}/metadata (admin|user|auditor)
- DELETE /keys/{id} (admin) -> soft-deactivate
- POST /encrypt (admin|user)
  body: { key_id, plaintext_b64, aad_b64? }
- POST /decrypt (admin|user)
  body: { key_id, ciphertext_b64, aad_b64? }
- GET /audits (admin|auditor)
  query: tenant_id?, action?, actor_id?, success?, limit?

Security notes
- BYOK material is never stored in plaintext; it is wrapped with the selected KMS provider.
- Encryption context binds wrapped keys to (tenant_id, key_id, name).
- AES-GCM used for both local KMS wrapping and data encryption.
- Do not send secrets in audit messages.

Local KMS details
- Uses a 256-bit master key stored base64 in local_kms_master.key by default.
- Override with env LOCAL_KMS_MASTER_KEY_B64 or set LOCAL_KMS_MASTER_KEY_PATH.

AWS KMS
- Set AWS_KMS_KEY_ID and AWS credentials env.
- If AWS KMS init fails, app falls back to local KMS.

Example curl
- Import BYOK (admin):
  curl -s -X POST http://localhost:5000/keys/import \\
    -H 'Content-Type: application/json' \\
    -H 'X-User-Id: alice' -H 'X-User-Role: admin' \\
    -d '{"name":"cust-key-1","tenant_id":"t1","key_material_b64":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="}'

- Encrypt (user in tenant):
  curl -s -X POST http://localhost:5000/encrypt \\
    -H 'Content-Type: application/json' \\
    -H 'X-User-Id: bob' -H 'X-User-Role: user' -H 'X-Tenant-Id: t1' \\
    -d '{"key_id":"<id>","plaintext_b64":"SGVsbG8gV29ybGQh"}'

- Decrypt:
  curl -s -X POST http://localhost:5000/decrypt \\
    -H 'Content-Type: application/json' \\
    -H 'X-User-Id: bob' -H 'X-User-Role: user' -H 'X-Tenant-Id: t1' \\
    -d '{"key_id":"<id>","ciphertext_b64":"<from_encrypt>"}'

Testing roles
- user requires X-Tenant-Id
- auditor can view metadata and audits but cannot encrypt/decrypt or modify keys

Disclaimer
- This sample is for demonstration only. For production, add proper authentication, secure secret management, request rate limiting, structured logging, and comprehensive monitoring.

