Auth & RBAC Scaffold (Flask)

Features:
- Local auth with email/password
- JWT access and refresh tokens, revocation/blacklist
- RBAC with Roles and Permissions
- OAuth2/OIDC SSO connectors (Google, GitHub, Generic OIDC like Okta/Azure AD)

Quick start:
1) python -m venv .venv && source .venv/bin/activate
2) pip install -r requirements.txt
3) cp .env.example .env and fill in values
4) python run.py

Endpoints:
- POST /auth/register {email,password,name}
- POST /auth/login {email,password}
- POST /auth/refresh {refresh_token}
- POST /auth/logout (Authorization: Bearer <access>) optionally body {refresh_token}
- GET /auth/me (Authorization: Bearer <access>)
- GET /oauth/<provider>/login
- GET /oauth/<provider>/callback
- GET /api/public
- GET /api/admin/secret (role: admin)
- GET /api/perms/secret (permission: view:secret)

Notes:
- Token is expected in Authorization header: Bearer <token>.
- Modify seed.py to adjust default roles/permissions.
- For OIDC (Okta/Azure), set OIDC_SERVER_METADATA_URL to issuer well-known, e.g., https://{domain}/.well-known/openid-configuration

