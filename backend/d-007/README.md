SBOM generation and attachment to release artifacts

Overview
- A minimal Flask service to:
  - Create releases
  - Upload artifacts to releases
  - Generate a CycloneDX SBOM for a release (artifacts + Python requirements)
  - Store and serve the SBOM alongside release artifacts

Endpoints
- GET /health
- GET /releases
- POST /releases
  - body: { "version": "1.2.3", "notes": "optional" }
- GET /releases/<version>
- POST /releases/<version>/artifacts
  - multipart/form-data: file=<artifact>
- GET /releases/<version>/artifacts/<filename>
- POST /releases/<version>/sbom
  - optional JSON body: { "requirements": "inline requirements.txt contents" }
- GET /releases/<version>/sbom

Storage
- Uses local filesystem by default under ./data/releases/<version>
- Configure base path via env STORAGE_DIR

SBOM
- CycloneDX JSON 1.5 stored at sbom.cdx.json in the release directory
- Includes components for uploaded artifact files
- Parses requirements.txt if present or provided inline to include Python library components

Run locally
- python -m venv .venv && source .venv/bin/activate
- pip install -r requirements.txt
- python app.py

Example flow
1) Create a release
   curl -sX POST localhost:8000/releases -H 'Content-Type: application/json' \
     -d '{"version":"1.0.0","notes":"Initial"}'

2) Upload an artifact
   curl -sF 'file=@dist/myapp-1.0.0.tar.gz' localhost:8000/releases/1.0.0/artifacts

3) Generate SBOM (using inline requirements)
   curl -sX POST localhost:8000/releases/1.0.0/sbom -H 'Content-Type: application/json' \
     -d '{"requirements":"flask==2.3.3\nrequests>=2.31.0"}'

4) Fetch SBOM
   curl -s localhost:8000/releases/1.0.0/sbom | jq .

Notes
- This is a minimal implementation for demonstration. For production-grade SBOMs, integrate with vetted SBOM tooling (e.g., Syft, CycloneDX generators) and sign artifacts/SBOMs.

