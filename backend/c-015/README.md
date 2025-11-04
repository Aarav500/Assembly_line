Cloud Infra Scaffolding (Terraform, Helm, K8s manifests) from Manifest

Quickstart
- Python 3.11+
- pip install -r requirements.txt
- python app.py
- POST /generate with YAML/JSON manifest to receive a zip of scaffolding.
- Or CLI: python cli.py examples/manifest.yaml -o ./out

Manifest Schema (example)
project:
  name: sample-app
  cloud: aws
  region: us-east-1
k8s:
  namespace: sample
  deployments:
    - name: api
      image: ghcr.io/acme/api:1.0.0
      replicas: 2
      ports: [8080]
      env:
        LOG_LEVEL: info
      resources:
        requests:
          cpu: "250m"
          memory: "256Mi"
        limits:
          cpu: "500m"
          memory: "512Mi"
  services:
    - name: api
      type: ClusterIP
      port: 80
      targetPort: 8080
  ingress:
    enabled: true
    className: nginx
    annotations:
      nginx.ingress.kubernetes.io/ssl-redirect: "true"
    hosts:
      - host: api.example.com
        paths: ["/"]
    tls:
      - secretName: api-tls
        hosts: ["api.example.com"]
terraform:
  backend:
    type: s3
    bucket: my-tf-state-bucket
    key: sample-app/terraform.tfstate
    region: us-east-1
    dynamodb_table: tf-locks
helm:
  chart:
    name: sample-app
    version: 0.1.0
    appVersion: 1.0.0
  values:
    image:
      pullPolicy: IfNotPresent

Outputs
- helm/<chart>/Chart.yaml, values.yaml, templates/*
- k8s/*.yaml (namespace, deployments, services, ingress)
- terraform/<cloud> (backend, providers, variables, main placeholder)

