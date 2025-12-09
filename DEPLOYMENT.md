# Deployment and Access Notes

This environment does not have outbound network access or the ability to expose publicly reachable URLs, so I cannot deploy the stack to a remote host or provide an external link. You can, however, run the application locally using Docker Compose or the lightweight local runners that mirror the container health endpoints.

## Run the full stack with Docker Compose
1. Ensure Docker and Docker Compose are installed.
2. Provide the required environment values in a `.env` file (database credentials, `BACKEND_URL`, `FRONTEND_URL`, `VM_PUBLIC_IP`, etc.).
3. From the repository root, build and launch the services:
   ```bash
   docker-compose up --build
   ```
4. After the containers report healthy, access:
   - **Primary entrypoint:** http://localhost/ (nginx now points this to the frontend control plane so you have a visible landing page.)
   - API via nginx: http://localhost/api/ (routes to the backend)
   - Infrastructure dashboard: http://localhost/infra/
   - Backend control plane directly: http://localhost:5000/
   - Frontend control plane directly: http://localhost:3000/

## Run lightweight local health servers (no Docker)
For quick checks without Docker, you can use the Flask-based runners added previously:

```bash
# Terminal 1
python backend/local_run.py

# Terminal 2
python frontend/local_run.py

# Terminal 3
python infrastructure/local_run.py
```

The local dashboard will poll the backend and frontend health endpoints and render a status page at http://localhost:8080/.
