File upload & storage scaffolds with signed URLs and lifecycle policies

Quickstart
- Python 3.10+
- Copy .env.example to .env and edit
- pip install -r requirements.txt
- python app.py

API
- POST /api/files/presign-upload
  body: { filename, content_type, content_length, metadata?, prefix? }
  returns presigned URL for direct upload to S3 or local dev endpoint

- GET /api/files/presign-download?key=...&as_attachment=true&filename=my.pdf
  returns signed URL to download

Local backend
- Upload: PUT to /_local/upload?token=... with header Content-Type and Content-Length and body as raw file bytes
- Download: GET /_local/download/<key>?token=...

S3 lifecycle
- See infra/s3-lifecycle.json and scripts/apply_lifecycle.sh to apply lifecycle config to your bucket

Security notes
- Restrict allowed MIME prefixes via ALLOWED_MIME_PREFIXES
- Keep APP_SECRET_KEY secret
- Use private ACL for S3 (default)
- Validate keys on download from your DB if mapping files to users

