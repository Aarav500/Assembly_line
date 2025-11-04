Model Access Policies and Per-Tenant Quotas (Flask)

Quick start
- Python 3.10+
- pip install -r requirements.txt
- python run.py
- Service listens on http://localhost:8000

Key concepts
- Tenants: organizations/accounts
- Users: belong to a tenant and have roles
- API keys: authenticate users and identify tenant context
- Models: registry of available model names
- Policies: per-tenant access rules for models, optionally constrained by user roles
- Quotas: per-tenant call limits per period (daily/monthly)

Admin API examples
1) Create tenant
curl -sX POST http://localhost:8000/admin/tenants -H 'Content-Type: application/json' -d '{"name":"acme"}'

2) Create user and API key (replace TENANT_ID)
curl -sX POST http://localhost:8000/admin/users -H 'Content-Type: application/json' -d '{"email":"alice@acme.com","role":"admin","tenant_id":TENANT_ID}'
# Save the returned api_key

3) Register models
curl -sX POST http://localhost:8000/admin/models -H 'Content-Type: application/json' -d '{"name":"gpt-4o"}'
curl -sX POST http://localhost:8000/admin/models -H 'Content-Type: application/json' -d '{"name":"embedding-1"}'

4) Set access policy for tenant
curl -sX POST http://localhost:8000/admin/policies -H 'Content-Type: application/json' -d '{"tenant_id":TENANT_ID,"model_name":"gpt-4o","allowed":true,"roles_allowed":["admin","member"]}'

5) Set quotas (daily and monthly)
curl -sX POST http://localhost:8000/admin/quotas -H 'Content-Type: application/json' -d '{"tenant_id":TENANT_ID,"period":"daily","max_calls":1000}'
curl -sX POST http://localhost:8000/admin/quotas -H 'Content-Type: application/json' -d '{"tenant_id":TENANT_ID,"period":"monthly","max_calls":10000}'

6) View tenant summary
curl -s http://localhost:8000/admin/tenants/TENANT_ID/summary

Invoke model
Replace API_KEY and ensure policy + quotas are configured.

curl -sX POST http://localhost:8000/invoke \
 -H 'Content-Type: application/json' \
 -H 'Authorization: Bearer API_KEY' \
 -d '{"model":"gpt-4o","input":"Hello"}'

Notes
- Quotas are enforced across all models for a tenant; you can create both daily and monthly quotas and both must have remaining calls for a request to pass.
- Policies default to deny if no policy exists for a given tenant+model.
- roles_allowed is optional; if provided, the user role must be in the list.
- This demo uses SQLite and simple counters; production systems should add row-level locking and robust concurrency controls.

