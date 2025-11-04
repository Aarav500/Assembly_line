CDN integration & automated cache invalidation on deploys

- Stack: Python (Flask)
- Features:
  - Sensible Cache-Control and Surrogate-Control headers
  - Surrogate-Key/Cache-Tag headers for tag-based purging
  - ETag support for conditional requests
  - Scripts to purge caches across Cloudflare, Fastly, and AWS CloudFront
  - GitHub Actions workflow example triggering purges post-deploy

Quick start

- Create a virtualenv and install requirements
- Copy .env.example to .env and fill in your settings
- Run the app: python run.py

CDN purge

- Purge manually: python scripts/purge_cdn.py --provider fastly --keys app:cdn-demo-app
- Post-deploy purge: python scripts/post_deploy.py

Environment variables

- CDN_PROVIDER: cloudflare|fastly|cloudfront
- For provider-specific credentials, see .env.example

Surrogate keys

- app:{APP_NAME}
- release:{RELEASE_SHA}
- route-specific keys, e.g., route:index, route:api:data

Notes

- Cloudflare tag purge requires an Enterprise plan
- CloudFront does not support tag-based purges; use paths or /*

