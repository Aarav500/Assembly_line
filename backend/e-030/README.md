kubernetes-operator-scaffolding-generator-for-app-specific-o

Kubernetes operator scaffolding generator for app-specific ops (Python + Flask).

Features:
- HTTP API and CLI to generate a Python Kopf-based Kubernetes Operator scaffold
- Customizable CRD Group/Version/Kind and plural
- App-specific operation stubs
- Deploy manifests (CRD, RBAC, Deployment), Dockerfile, Makefile

Quickstart:
1) Install
   pip install -e .

2) Serve API
   kosg-serve --host 0.0.0.0 --port 8000

3) Generate via API
   curl -sS -X POST http://localhost:8000/generate?format=json \
     -H 'Content-Type: application/json' \
     -d '{
           "app_name":"MyApp",
           "group":"apps.example.com",
           "version":"v1alpha1",
           "kind":"MyApp",
           "operations":["reconcile","scale","backup"]
         }' | jq .

4) CLI generation to directory
   kosg-generate --config payload.json --out-dir ./out

Payload schema (partial):
- app_name: string (required)
- group: string, e.g. apps.example.com
- version: string, e.g. v1alpha1
- kind: string, e.g. MyApp
- plural: string (optional; auto if omitted)
- description: string
- author_name: string
- author_email: string
- license: string (SPDX)
- image: string (operator container image)
- python_version: string (default 3.11)
- include_examples: boolean (default true)
- operations: array of strings (stubs will be generated)

API
- POST /generate?format=json|zip
  - Body: JSON payload
  - Returns: Either a JSON map of files or a zip archive

License: MIT

