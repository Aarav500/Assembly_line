Dataset Management & Data Quality Profiling Dashboards

Stack: Python, Flask

Features:
- Upload CSV datasets
- List datasets with quick stats
- Detailed profiling per dataset: missingness, duplicates, per-column stats, histograms, categorical distributions, correlations
- Cached profiling JSON per dataset
- Download and delete datasets

Quickstart:
1. python -m venv .venv && source .venv/bin/activate (Windows: .venv\\Scripts\\activate)
2. pip install -r requirements.txt
3. export FLASK_APP=app.py (Windows PowerShell: $env:FLASK_APP="app.py")
4. flask run

Then open http://localhost:5000

Config:
- Edit config.py to adjust directories and EAGER_PROFILE.

Notes:
- Only CSV uploads are supported.
- For large datasets, profiling may take time.

