# Flask Template

A production-ready Flask template with Docker, Gunicorn, CORS, testing, and basic routes.

Quickstart:
- make install
- cp .env.example .env
- make dev  # http://localhost:8000

Docker:
- docker compose up --build

Endpoints:
- GET / -> basic info
- GET /health -> liveness
- GET /ready -> readiness
- GET /api/v1/hello?name=YourName
- POST /api/v1/echo {"foo": "bar"}

