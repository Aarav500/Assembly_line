# Local service smoke test

The stack's Flask control planes can be verified without Docker by running each service on a local port and curling the health endpoints.

## Commands

```bash
PORT=5000 python backend/app.py >/tmp/backend.log 2>&1 & BACK_PID=$!
BACKEND_URL=http://localhost:5000 FRONTEND_URL=http://localhost:3000 VM_PUBLIC_IP=localhost PORT=8080 \
  python infrastructure/app.py >/tmp/infrastructure.log 2>&1 & INFRA_PID=$!
BACKEND_API_URL=http://localhost:5000 INFRA_URL=http://localhost:8080 PORT=3000 \
  python frontend/app.py >/tmp/frontend.log 2>&1 & FRONT_PID=$!

curl -s http://localhost:5000/health
curl -s http://localhost:3000/health
curl -s http://localhost:8080/health

kill $BACK_PID $INFRA_PID $FRONT_PID
```

Expected outputs show each service reporting `"status": "healthy"`.
