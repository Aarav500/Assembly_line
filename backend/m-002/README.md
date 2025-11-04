Staging Demo Data Generator (Flask)

Quickstart
- python -m venv .venv && source .venv/bin/activate
- pip install -r requirements.txt
- cp .env.example .env
- Edit .env as needed (APP_ENV=staging for staging; set DEMO_DATA_TOKEN)
- python app.py
- Open http://localhost:5000/admin/demo-data

Notes
- The generator is gated to staging. For local dev, set ALLOW_DEMO_DATA=true in .env.
- If DEMO_DATA_TOKEN is set, you must provide it in the UI field.
- The Generate action will top-up to the target counts. Use the Reset checkbox to wipe existing demo data first.

