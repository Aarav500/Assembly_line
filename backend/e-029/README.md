Backup Retention Compliance Automation and Evidence Packaging

Overview
- Flask-based service to automate backup retention compliance checks and enforcement.
- Generates tamper-evident evidence packages (ZIP) with manifest and action logs.

Quick start
- Python 3.9+
- pip install -r requirements.txt
- ./run.sh

Key endpoints
- GET /health
- GET /backups
- POST /backups/simulate {"size_kb": 64, "label": "nightly"}
- GET /policies
- POST /policies {"policy": {"retain_days": 30, "min_backups": 7, "max_backups": 100, "require_frequency_hours": 24}}
- POST /compliance/check
- POST /compliance/enforce {"dry_run": false, "note": "weekly-cleanup"}
- POST /evidence/package {"note": "monthly-audit"}
- GET /evidence/<event_id>/download
- GET /compliance/history

Policy fields
- retain_days: keep backups for at least N days
- min_backups: minimum number of backups to retain
- max_backups: hard cap on number retained (oldest purged first)
- require_frequency_hours: expected backup frequency; large gaps are flagged
- backup_dir: directory to scan for backups (defaults to data/backups)

Backups
- The service scans files in backup_dir; filenames matching backup-YYYYmmddHHMMSS.* help infer timestamp.
- Use /backups/simulate to create sample backups for testing.

Evidence packages
- Created for enforcement and ad-hoc packaging.
- Include manifest.json (policy, compliance result, inventory before/after), actions.json, README.txt.
- Zip path returned in API response; downloadable via /evidence/<id>/download.

Data locations
- data/app.db: SQLite database
- data/backups: backup files
- data/evidence: evidence directories and zips

Security note
- This demo deletes files only within backup_dir; validate and secure in production.

