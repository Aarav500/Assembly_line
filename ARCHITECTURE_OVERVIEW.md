# Architecture Overview

## Repository layout
- **backend/**: 400+ backend modules grouped in numbered folders plus `_shared` utilities for cross-module imports (see `backend/README_IMPORTS.md`).
- **frontend/**: matching numbered folders for UI modules and a `_shared` helper area; follows the same import conventions as the backend (`frontend/README_IMPORTS.md`).
- **infrastructure/**: operational tooling (monitoring, deployment helpers) organized in scenario folders with a `_shared` utility area.
- **database/** and **redis** volumes: stateful data for Postgres and Redis provisioned by Docker Compose (`database/init.sql` initializes the database).
- **nginx/**: reverse-proxy configuration that fronts the services.
- **docker-compose.yml**: orchestrates the full stack (backend, frontend, infra dashboard, Postgres, Redis, Nginx) for a VM or local run.
- **DEPLOYMENT.md**: environment notes and how to bring up the stack with Docker or the light `local_run.py` helpers.

## How services fit together
The VM stack is defined in `docker-compose.yml`:
- **Backend (port 5000)** builds `backend/Dockerfile`, provisions per-module virtualenvs via `smart_venv_manager.py`, and exposes `/health` plus `/modules` for visibility into the module-to-venv mapping. It depends on Postgres and Redis and mounts persistent `data` and `logs` volumes.
- **Frontend (port 3000)** builds `frontend/Dockerfile`, reads `BACKEND_API_URL` from the environment to call the backend, and reports readiness on `/health`.
- **Infrastructure dashboard (port 8080)** builds `infrastructure/Dockerfile` and polls the backend/frontend health URLs (configured via `BACKEND_URL` and `FRONTEND_URL`) to surface status; it also mounts Docker socket read-only for observability tooling.
- **Postgres (port 5432)** seeds from `database/init.sql` and is referenced by `DATABASE_URL`/`DB_*` variables shared with the backend and infra services.
- **Redis (port 6379)** provides caching/queueing and is referenced via `REDIS_URL`.
- **Nginx (port 80)** proxies `/api/` to the backend, `/infra/` to the infrastructure dashboard, and `/` to the frontend using `nginx/nginx.conf`.

## Module shape inside each service
- Each service directory contains many numbered modules (e.g., `backend/a-001`, `frontend/infra-001`) with an `app.py` entrypoint. Shared code lives under `_shared/` for imports that span modules.
- The `import_helper.py` / README guidance in backend and frontend shows how to bootstrap imports or run modules from the project root to keep `PYTHONPATH` aligned.
- The Dockerfiles create a health endpoint (`/health`) and a `run_module.sh` helper that activates the correct virtualenv before executing a module script. The mapping lives in `venv_mapping.json` generated at build time.

## Running on a VM
1. Create a `.env` at repo root with database, Redis, and service URLs. Common values: `DATABASE_URL=postgresql://<user>:<pass>@db:5432/<db>`, `REDIS_URL=redis://redis:6379/0`, `BACKEND_URL=http://backend:5000`, `FRONTEND_URL=http://frontend:3000`, `VM_PUBLIC_IP` for logging, and secrets like `SECRET_KEY`.
2. From the VM, run `docker-compose up --build` to start all services; health checks will gate dependencies until ready.
3. Verify via the exposed ports or through Nginx: backend at `http://localhost:5000/health`, frontend at `http://localhost:3000/health`, infrastructure dashboard at `http://localhost:8080/` or `http://localhost/infra/` through Nginx.
4. For lightweight debugging without containers, run `python backend/local_run.py`, `python frontend/local_run.py`, and `python infrastructure/local_run.py` in separate shells; the infra dashboard will poll the other two.

## How pieces interact at runtime
- Frontend requests flow through Nginx → frontend container → backend API (using `BACKEND_API_URL`).
- Backend business modules use Postgres/Redis connections from the shared `.env` values and can be executed directly with `run_module.sh <module> app.py` inside the container to pick the correct virtualenv.
- Infrastructure service monitors the backend/frontend health endpoints and has read-only Docker socket access for metrics; its `/health` endpoint surfaces aggregated status.
- Logs and data directories are volume-mounted (`backend_logs`, `frontend_logs`, `infra_logs`, `backend_data`, etc.) so container restarts on the VM preserve state.
