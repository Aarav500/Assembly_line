Minimal infra to run a Python/Flask app via Docker Compose or Kubernetes.

Assumptions
- Your Flask application exposes a WSGI application object named `app` in a module named `app` (i.e., `app.py` defines `app = Flask(__name__)`).
- If different, set APP_MODULE accordingly (e.g., `myapp:create_app()` would be `APP_MODULE=myapp:create_app()`).

Docker Compose
1) Build and run:
   APP_MODULE=app:app docker compose up --build
   # App available at http://localhost:8000

2) Customization via env vars (with defaults):
   - APP_MODULE=app:app
   - GUNICORN_WORKERS=2
   - GUNICORN_TIMEOUT=60
   - GUNICORN_LOGLEVEL=info

Kubernetes
1) Build and push an image:
   docker build -t your-dockerhub-username/flask-app:latest .
   docker push your-dockerhub-username/flask-app:latest

2) Deploy with kustomize:
   kubectl apply -k k8s/

3) Port-forward to test locally:
   kubectl port-forward svc/flask-app 8000:80
   # App available at http://localhost:8000

Notes
- Healthchecks probe `/` by default. If you provide `/healthz`, update the compose and k8s manifests for more robust checks.
- If your app requires extra system packages or build tools, extend the Dockerfile accordingly.

