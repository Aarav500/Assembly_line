Blue/Green Deployment Support with Traffic Switching (Flask)

How it works:
- Both BLUE and GREEN handlers are present in the same service for simplicity.
- Requests to / and /api/hello are routed to BLUE or GREEN based on:
  1) Forced variant via query param ?variant=blue|green or header X-BG-Variant.
  2) Sticky cookie bg_variant (if respect_sticky=true).
  3) Random split controlled by blue_percent in config/traffic.json.

Run:
- pip install -r requirements.txt
- python app.py

Admin (optional auth via env ADMIN_TOKEN):
- GET  /admin/config
- POST /admin/config {"blue_percent": 80, "respect_sticky": true, "cookie_max_age": 86400}
- POST /admin/switch (toggle 0%/100%)
- POST /admin/promote {"version": "green"}
- POST /admin/rollback (100% blue)
- POST /admin/respect_sticky {"respect_sticky": false}

Debug:
- GET /whoami to see decision and cookie.
- GET /blue and /green hit versions directly.

Notes:
- Persisted config stored at config/traffic.json (override path via TRAFFIC_CONFIG env var).
- Sticky cookie name: bg_variant.

