dns--domain-provisioning-automation-with-acme-certs

Description: DNS & domain provisioning automation with ACME certs
Stack: python, flask

Quick start
- Python 3.10+
- pip install -r requirements.txt
- Copy .env.example to .env and adjust settings
- Ensure CERTBOT is installed (https://certbot.eff.org/) if you want real Let's Encrypt certificates
- Run: python run.py

API
- POST /api/domains
  Body: { "name": "example.com", "provider": { "name": "cloudflare", "config": { "api_token": "..." } } }
- GET /api/domains
- GET /api/domains/:id
- POST /api/domains/:id/issue_cert
  Body: { "alt_names": ["www.example.com"] }
- GET /api/jobs/:job_id

Providers
- mock: no-op DNS provider for testing
- cloudflare: uses API token (CLOUDFLARE_API_TOKEN or provider.config.api_token)

ACME
- Default uses Let's Encrypt staging via certbot with manual DNS hooks that call the configured DNS provider
- For production, set ACME_DIRECTORY_URL to https://acme-v02.api.letsencrypt.org/directory
- For local development without certbot or DNS, set ENABLE_SELF_SIGNED=true

Storage
- Certificates are placed under STORAGE_DIR/certs/<domain>/ (cert.pem, chain.pem, fullchain.pem, privkey.pem)
- Certbot data (if used) is under STORAGE_DIR/certbot/

Notes
- Certbot must be installed on the host and accessible via CERTBOT_BIN
- Cloudflare token requires permissions: Zone:Read and DNS:Edit on the relevant zones
- The project uses DNS-01, so no web server access is required

