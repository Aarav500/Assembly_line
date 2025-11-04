Audit & Compliance Export Bundles for External Auditors

Overview
- Flask API to generate signed, self-contained ZIP bundles of compliance artifacts (policies, controls, evidences, audit logs, users) for external auditors.

Quickstart
1) Install dependencies: pip install -r requirements.txt
2) Seed sample data: python seed_data.py
3) Start API: AUDIT_API_TOKEN=dev-token python app.py
4) Create a bundle:
   curl -X POST http://localhost:5000/api/bundles \
     -H 'Authorization: Bearer dev-token' \
     -H 'Content-Type: application/json' \
     -d '{"frameworks":["SOC2"],"anonymize_pii":true,"label":"Q4 External"}'
5) List bundles: curl -H 'Authorization: Bearer dev-token' http://localhost:5000/api/bundles
6) Download bundle: curl -L -H 'Authorization: Bearer dev-token' http://localhost:5000/api/bundles/<id>/download -o bundle.zip

Env Vars
- AUDIT_API_TOKEN: Bearer token for API access (required)
- DATABASE_URL: Path to sqlite DB (default data/app.db)
- EXPORT_DIR: Directory to write ZIP bundles (default data/exports)
- SIGNING_KEY: If set, adds HMAC-SHA256 signature of manifest.json into bundle
- APP_VERSION: Version string embedded in manifest

Bundle Content
- data/*.jsonl: line-delimited records per entity
- manifest.json: bundle metadata, filters, and file checksums
- checksums.txt: SHA256 for each data file
- signature.json: present if SIGNING_KEY is set
- README.txt: usage instructions

Notes
- Time filters expect ISO 8601 (e.g., 2024-01-01T00:00:00Z)
- Framework filtering applies to policies and their child controls/evidences
- PII anonymization pseudonymizes user names/emails and audit log actors

