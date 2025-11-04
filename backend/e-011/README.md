Auto-setup of Kubernetes Ingress with TLS certificate management using cert-manager (ACME) for a Flask app.

Quickstart:
- Build image: docker build -t YOUR_IMAGE:tag .
- Push to registry and set IMAGE to that reference.
- Install ingress controller: bash scripts/install-ingress-nginx.sh
- Install cert-manager: bash scripts/install-cert-manager.sh
- Point your DOMAIN DNS A/AAAA/CNAME to the ingress controller external IP/hostname.
- Deploy (staging): ENVIRONMENT=staging APP_NAME=flask-app NAMESPACE=web IMAGE=YOUR_IMAGE:tag DOMAIN=your.domain.com LETSENCRYPT_EMAIL=you@example.com bash scripts/deploy.sh
- After staging works, switch to production issuer: ENVIRONMENT=prod ... bash scripts/deploy.sh

Files:
- app/: Flask app with health endpoints.
- k8s/templates/: Kubernetes manifests templates (namespace, deployment, service, ingress, cluster issuers).
- scripts/: Install ingress-nginx, install cert-manager, and deploy with envsubst rendering.

Notes:
- Uses HTTP-01 ACME challenge via ingress-nginx.
- Ensure your cluster supports LoadBalancer for the ingress service or adapt values for your environment.
- Change replicas, resources, and other settings as needed.

