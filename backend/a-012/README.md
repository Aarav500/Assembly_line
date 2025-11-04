Quick Smoke Tests (Flask)

Description
- Run quick smoke tests locally (auto-start Flask app) or against a remote sandbox (existing deployment).
- Reports pass/fail for core features and exits with proper code for CI usage.

Project structure
- app/: Minimal Flask app with core endpoints used by smoke tests.
- smoke/run_smoke.py: CLI to run smoke tests locally or against a remote base URL.
- wsgi.py: Entry point to run the Flask dev server manually.

Install
- python -m venv .venv && . .venv/bin/activate
- pip install -r requirements.txt

Run locally (auto-start app)
- python smoke/run_smoke.py --mode local
- Options: --port 5001, --timeout 5, --wait 10

Run against sandbox (remote)
- python smoke/run_smoke.py --mode remote --base-url https://sandbox.example.com
- Add --insecure to skip TLS verification if needed.

Exit codes
- 0: all tests passed
- 1: at least one test failed
- 2: invalid arguments
- 3: local server failed to start

Endpoints exercised
- GET /health -> {"status":"ok"}
- GET /api/version -> {"version":"..."}
- POST /api/echo -> {"echo": <your-payload>}
- GET/POST /api/items -> basic in-memory item lifecycle

Notes
- The in-memory store is for demo only and resets each local run.
- For remote runs, the items list may already contain data; the test only asserts the presence of the newly created item.

