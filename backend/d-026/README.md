KV-based feature flags in Flask

Usage
- Install: pip install -r requirements.txt
- Run: python app.py
- Flags are loaded from (precedence high->low):
  1) Environment variables with prefix FF_, e.g. FF_SEARCH_V2=true
  2) JSON file flags.json (modifiable at deployment time)

Endpoints
- GET /            -> shows current flag values
- GET /beta        -> enabled if beta_endpoint is true
- GET /search      -> returns v1 or v2 based on search_v2 flag

Admin (optional)
- Enable: set ENABLE_FLAG_ADMIN=true
- Optional security: set FLAG_ADMIN_TOKEN and send X-Admin-Token header
- GET /admin/flags               -> list flags (with overrides applied)
- PUT /admin/flags/<name>        -> body {"value": true|false|"string"} persists to flags.json

CLI for deployment-time changes
- List: python manage_flags.py list -f flags.json
- Get:  python manage_flags.py get search_v2 -f flags.json
- Set:  python manage_flags.py set search_v2 true -f flags.json
- Unset:python manage_flags.py unset search_v2 -f flags.json

Environment variables
- FEATURE_FLAGS_FILE: path to JSON file (default ./flags.json)
- FEATURE_FLAGS_ENV_PREFIX: prefix for env flags (default FF_)
- FEATURE_FLAG_DEFAULT: default for missing flags (true/false, default false)
- ENABLE_FLAG_ADMIN: enable write endpoints (default false)
- FLAG_ADMIN_TOKEN: optional token required via X-Admin-Token header

Docker
- docker build -t flags-app .
- docker run -p 8000:8000 -e FF_BETA_ENDPOINT=true flags-app

