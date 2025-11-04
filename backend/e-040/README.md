Infrastructure Compliance Scanner Reporting & Remediation Workflows

Quickstart
- pip install -r requirements.txt
- python run.py
- Seed sample data: python scripts/seed.py

Key Endpoints
- Health: GET /health
- Assets: GET/POST /api/assets, GET /api/assets/<id>, GET /api/assets/<id>/findings
- Rules: GET/POST /api/rules, GET /api/rules/<id>
- Scans: POST /api/scans, GET /api/scans, GET /api/scans/<id>, POST /api/scans/<id>/ingest, POST /api/scans/<id>/finalize
- Findings: GET /api/findings, GET /api/findings/<id>, PATCH /api/findings/<id>, POST /api/findings/bulk-update
- Remediations: GET /api/remediations, POST /api/remediations, GET /api/remediations/<id>, PATCH /api/remediations/<id>, POST /api/remediations/<id>/actions/<action_id>
- Reports: GET /api/reports/compliance-summary, GET /api/reports/assets, GET /api/reports/top-risky-assets

Example: Create a scan and ingest results
1) Create scan
curl -sX POST http://localhost:5000/api/scans -H 'Content-Type: application/json' -d '{"provider":"aws"}'

2) Ingest
curl -sX POST http://localhost:5000/api/scans/<scan_id>/ingest -H 'Content-Type: application/json' -d '{
  "assets": [
    {"id":"asset-a1","name":"i-abc","type":"ec2","provider":"aws","region":"us-east-1","tags":{"env":"prod"}}
  ],
  "findings": [
    {"asset_id":"asset-a1","rule":{"key":"CIS-1.1","title":"Ensure MFA is enabled","severity":"High","remediation_guidance":"Enable MFA."},"state":"Fail","details":{"mfa":false}}
  ]
}'

3) Finalize
curl -sX POST http://localhost:5000/api/scans/<scan_id>/finalize -H 'Content-Type: application/json' -d '{"status":"Completed"}'

Example: Create remediation plan
curl -sX POST http://localhost:5000/api/remediations -H 'Content-Type: application/json' -d '{
  "finding_ids": ["<finding_id>"] ,
  "owner": "alice@example.com",
  "summary": "Fix critical compliance gaps",
  "due_date": "2025-01-31T00:00:00Z"
}'

