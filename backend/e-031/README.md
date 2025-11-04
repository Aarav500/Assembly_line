# Auto-rotate machine credentials and revoke on breach detection

This service issues machine credentials, auto-rotates them on a schedule, validates them, and revokes/rotates on breach detection.

- Stack: Python, Flask, SQLAlchemy, cryptography
- Storage: SQLite (default) or any SQLAlchemy-compatible DB
- Encryption: Symmetric using Fernet (AES-128 in CBC with HMAC/SHA256, via cryptography)

## Quick start

1. Generate an encryption key

   python scripts/generate_key.py

   Set ENCRYPTION_KEY to the printed value.

2. Configure environment (optional): copy .env.example and export variables

3. Install dependencies

   pip install -r requirements.txt

4. Run

   python app.py

The service exposes:

- POST /api/credentials (admin) create a credential
- GET /api/credentials/{id} (admin) inspect metadata
- POST /api/credentials/{id}/rotate (admin) manual rotation
- POST /api/credentials/{id}/revoke (admin) revoke current version (optionally disable)
- POST /api/credentials/{id}/breach (admin) revoke + rotate immediately
- POST /api/validate validate credentials
- GET /health health check

Admin endpoints require header: X-API-Key: <ADMIN_API_KEY>

## Notes

- Secrets are returned only at creation/rotation time and stored encrypted at rest.
- Automatic rotation runs in a background thread checking periodically.
- Audit events are stored in DB and logs/audit.log.

