Edge CDNs & Pre-render Jobs for Static Site Publishing (Flask)

Overview
- Flask app with demo pages (/, /about, /blog/<slug>)
- Pre-render jobs that crawl specified paths and write static HTML to builds/<site_slug>
- Incremental: only changed pages are written and purged from the CDN
- CDN providers: noop (default), Cloudflare, Fastly (configurable via env)
- Simple job queue with background workers and job status API

Quickstart
1) Install dependencies
   pip install -r requirements.txt

2) Configure (optional)
   cp .env.example .env
   # adjust values or export env vars in your shell

3) Run server
   python run.py

4) Register a site (optional; if omitted, default routes are used)
   curl -X POST http://localhost:5000/api/v1/sites \
     -H 'Content-Type: application/json' \
     -d '{"slug":"mysite","routes":["/","/about","/blog/hello-world","/blog/edge-cdn-primer"]}'

5) Trigger a pre-render job
   curl -X POST http://localhost:5000/api/v1/prerenders \
     -H 'Content-Type: application/json' \
     -d '{"site_slug":"mysite"}'

6) Check job status
   curl http://localhost:5000/api/v1/jobs
   curl http://localhost:5000/api/v1/jobs/<job_id>

Build outputs
- Static files are written to builds/<site_slug>/...
- A manifest.json records SHA-256 fingerprints per path for incremental updates.

CDN purge
- Set CDN_PROVIDER to 'cloudflare' or 'fastly' and configure corresponding credentials.
- Set CDN_BASE_URL to the canonical site base (e.g., https://www.example.com) so URLs can be purged.
- Only pages that changed are purged.

Environment variables
- BUILD_ROOT: Directory for build outputs (default: ./builds)
- DATA_DIR: SQLite DB location (default: ./data)
- CDN_PROVIDER: noop | cloudflare | fastly (default: noop)
- CDN_BASE_URL: Required for non-noop providers (e.g., https://example.com)
- CF_API_TOKEN, CF_ZONE_ID: Cloudflare credentials
- FASTLY_API_KEY, FASTLY_SERVICE_ID: Fastly credentials
- JOB_WORKERS: Number of background workers (default: 1)
- LOG_LEVEL: Logging level (default: INFO)
- SECRET_KEY: Flask secret key

API summary
- GET  /healthz
- GET  /api/v1/sites
- POST /api/v1/sites               { slug, routes[] }
- POST /api/v1/prerenders          { site_slug, paths[]? }
- GET  /api/v1/jobs?limit&offset
- GET  /api/v1/jobs/{id}

Notes
- This demo pre-renders the Flask app's own routes using a test client. In production, you could adapt render_paths to snapshot an external site or a headless SPA.
- SQLite is used for simple persistence of sites and jobs.
- The job queue is in-process; for distributed processing, integrate Celery or RQ.

