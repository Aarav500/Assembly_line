Microservice decomposition advisor for Python/Flask monoliths.

How to run:
- pip install -r requirements.txt
- python app.py

API:
POST /analyze
Body JSON: {"path":"/abs/path"} or {"git_url":"https://..."}
Optional: include_tests (bool), thresholds (dict), project_name (str)
Or upload a repo archive as form-data field 'file'.

Returns JSON with candidates and a step-by-step decomposition plan.

