Blue/Green and Canary Orchestrations at Infra Layer (Traffic-Split) - Python/Flask

Overview
- Two backend Flask apps (blue and green) represent different versions.
- A router (infra layer) proxies traffic to blue/green based on orchestration strategy:
  - Blue/Green: routes 100% to active color.
  - Canary: splits traffic by weights between blue and green, with optional sticky sessions.
- Health checker avoids routing to unhealthy upstreams.

Quickstart
1) Install dependencies:
   pip install -r requirements.txt

2) Start backends in separate terminals:
   Terminal A:
     python apps/blue/app.py
   Terminal B:
     python apps/green/app.py

3) Start router (Terminal C):
   Environment variables (optional):
     export BLUE_URL=http://127.0.0.1:5001
     export GREEN_URL=http://127.0.0.1:5002
     export ROUTER_PORT=8080
   Run:
     python -m router.app

4) Send traffic to the router:
   curl -s http://127.0.0.1:8080/

Router API
- GET /health
  Router health and current orchestration state.

- GET /orchestration/status
  Current strategy, active color, and weights.

- POST /orchestration/strategy
  Body: {"strategy": "blue_green" | "canary"}

- POST /orchestration/bluegreen/activate
  Body: {"active": "blue" | "green"}

- POST /orchestration/canary/weights
  Body: {"blue": 80, "green": 20, "normalize": true}
  If normalize=true, values are normalized to sum 100.

- POST /orchestration/canary/shift
  Body: {"delta": 10, "towards": "green" | "blue"}
  Increases the weight of target by delta (clamped 0..100).

Headers and Sticky Sessions
- Provide X-Session-Key or a session_id cookie to keep users pinned consistently during canary rollout.
- Responses include routing metadata headers:
  - X-Routed-To: blue|green
  - X-Upstream-URL: upstream base URL

Security
- Optionally protect orchestration endpoints with a bearer token:
  export ORCH_TOKEN=your_token
  Then include Authorization: Bearer your_token in requests.

Env Vars
- BLUE_URL (default: http://127.0.0.1:5001)
- GREEN_URL (default: http://127.0.0.1:5002)
- ROUTER_HOST (default: 0.0.0.0)
- ROUTER_PORT (default: 8080)
- DEFAULT_STRATEGY (blue_green | canary; default blue_green)
- DEFAULT_ACTIVE (blue | green; default blue)
- DEFAULT_BLUE_WEIGHT (default 100)
- DEFAULT_GREEN_WEIGHT (default 0)
- ORCH_TOKEN (optional; protects /orchestration/*)
- STICKY_SESSIONS (true|false; default true)
- UPSTREAM_HEALTH_PATH (default /health)
- PROXY_TIMEOUT (seconds; default 10)

Examples
- Switch to canary with 90/10 split:
  curl -X POST http://127.0.0.1:8080/orchestration/strategy -H 'Content-Type: application/json' -d '{"strategy":"canary"}'
  curl -X POST http://127.0.0.1:8080/orchestration/canary/weights -H 'Content-Type: application/json' -d '{"blue":90, "green":10, "normalize": true}'

- Gradually shift 10% towards green:
  curl -X POST http://127.0.0.1:8080/orchestration/canary/shift -H 'Content-Type: application/json' -d '{"delta":10, "towards":"green"}'

- Blue/Green instant switch to green:
  curl -X POST http://127.0.0.1:8080/orchestration/strategy -H 'Content-Type: application/json' -d '{"strategy":"blue_green"}'
  curl -X POST http://127.0.0.1:8080/orchestration/bluegreen/activate -H 'Content-Type: application/json' -d '{"active":"green"}'

Notes
- This router is a lightweight Python reverse proxy to demonstrate infra-layer routing logic. In production, use or translate these concepts to your ingress/load balancer (e.g., NGINX, Envoy, Service Mesh) and automate orchestration via CI/CD.

