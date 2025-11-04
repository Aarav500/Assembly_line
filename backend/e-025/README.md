Environment Provisioning API (Flask)

Quickstart:
- pip install -r requirements.txt
- export ADMIN_API_KEY=change-me-admin
- python main.py

Admin endpoints:
- POST /api/v1/admin/teams {"name":"teamA"} -> returns api_key
- GET /api/v1/admin/teams

Team endpoints (use X-API-Key):
- GET /api/v1/me
- GET /api/v1/quotas
- POST /api/v1/environments {"name":"svc1","type":"dev","config":{}}
- GET /api/v1/environments
- GET /api/v1/environments/:id
- PATCH /api/v1/environments/:id
- DELETE /api/v1/environments/:id
- POST /api/v1/environments/:id/provision
- POST /api/v1/environments/:id/deprovision
- GET /api/v1/tasks
- GET /api/v1/tasks/:id
- GET /api/v1/audit

Health:
- GET /health

Notes:
- Uses SQLite by default at /data/app.db
- Provisioning and deprovisioning are simulated asynchronous tasks
- Quotas enforced per team per env type for requested/provisioning/active states

