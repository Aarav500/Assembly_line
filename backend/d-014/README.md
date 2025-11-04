GitOps Sync Job Generation and Validation (ArgoCD/Flux)

Endpoints:
- GET /healthz
- POST /generate/argocd-sync-job
- POST /generate/flux-reconcile-job
- POST /validate/job

ArgoCD request example (JSON):
{
  "appName": "my-app",
  "argocdServer": "argocd-server.argocd.svc.cluster.local:443",
  "auth": {"token": "<ARGOCD_TOKEN>"},
  "revision": "main",
  "prune": true,
  "wait": true,
  "waitTimeoutSeconds": 600,
  "jobNamespace": "jobs",
  "serviceAccountName": "argocd-sync",
  "image": "quay.io/argoproj/argocd:latest",
  "labels": {"team": "platform"},
  "annotations": {"janitor/ttl": "24h"}
}

Flux request example (JSON):
{
  "kind": "Kustomization",
  "name": "cluster-apps",
  "namespace": "flux-system",
  "withSource": true,
  "timeout": "5m",
  "jobNamespace": "jobs",
  "serviceAccountName": "flux-reconciler",
  "image": "ghcr.io/fluxcd/flux-cli:latest",
  "labels": {"team": "platform"}
}

Validation request example (JSON):
{
  "yaml": "apiVersion: batch/v1\nkind: Job\nmetadata:\n  name: example\nspec:\n  template:\n    spec:\n      restartPolicy: Never\n      containers:\n      - name: c\n        image: busybox"
}

Run locally:
- pip install -r requirements.txt
- FLASK_APP=app.main:app flask run --port 8000

Docker:
- docker build -t gitops-jobs .
- docker run -p 8000:8000 gitops-jobs

