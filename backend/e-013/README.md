Edge worker deployment templates for low-latency features

Structure:
- Flask app with low-latency patterns: caching headers, ETag, Server-Timing, streaming, and preload hints
- Dockerfile + gunicorn (gevent) for fast IO and Fly.io global deployment (edge-like)
- AWS CloudFront + Lambda@Edge templates (Terraform) to add edge logic (HTTPS redirect, query normalization, cookie stripping) and enrich response headers

Quick start (container):
1) docker build -t edge-flask .
2) docker run -p 8080:8080 edge-flask
3) curl http://localhost:8080/health

Fly.io (global):
- Set app name in fly.toml or export FLY_APP_NAME
- ./scripts/deploy_fly.sh

Lambda@Edge:
- Upload lambda code:
  export LAMBDA_BUCKET=your-bucket-in-us-east-1
  ./scripts/build_and_push_lambda.sh
- terraform -chdir=terraform init
- terraform -chdir=terraform apply -var origin_domain=your-origin.example.com -var lambda_bucket=your-bucket -var viewer_request_key=edge/viewer_request.zip -var viewer_response_key=edge/viewer_response.zip

Endpoints:
- GET /health
- GET /v1/edge-cached
- GET /v1/compute?input=abc&rounds=150000
- GET /v1/stream
- GET /v1/early-hints-sim
- GET /v1/cache/<key>, PUT /v1/cache/<key>?ttl=60 with {"value": ...}

Notes:
- Consider placing the container behind a CDN (CloudFront/Fastly/Cloudflare) for best latency.
- Tune caching policy and TTLs for your workload.

