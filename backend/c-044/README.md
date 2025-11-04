Auto-generate End-of-Day Maintenance Scripts (backup, vacuum, rotate logs)

Stack: Python, Flask

Overview:
- Exposes a simple API to generate end-of-day maintenance scripts that can:
  - Backup databases (PostgreSQL or SQLite)
  - VACUUM/ANALYZE (PostgreSQL, SQLite)
  - Rotate and prune logs
  - Install/uninstall a cron job to run the script at a specified time

Quickstart:
1) Create a virtualenv and install requirements:
   python -m venv venv && . venv/bin/activate
   pip install -r requirements.txt

2) Run the Flask app:
   export FLASK_APP=app.py
   flask run -p 5000

3) Generate scripts via API:
   curl -s -X POST http://localhost:5000/generate \
     -H 'Content-Type: application/json' \
     -d @examples/sample_config.json | jq

4) Navigate to the generated directory (generated/<job_name>/) and review files:
   - maintenance_<job_name>.sh
   - install_cron_<job_name>.sh
   - uninstall_cron_<job_name>.sh
   - .env (DB credentials)

5) Install the cron job:
   cd generated/<job_name>/
   bash install_cron_<job_name>.sh

Notes:
- The scripts are generated for Unix-like systems (bash, cron).
- Database credentials are stored in the generated .env file; ensure proper permissions.
- Backups and logs are written inside the generated job directory by default unless overridden.

