Quick-action panel: run CodeGen to add missing features, or start Fixer to patch failing tests

Stack: Python, Flask

How to run:
- Create a virtual environment and install dependencies: pip install -r requirements.txt
- Optionally set environment variables:
  - CODEGEN_CMD: shell command to execute for CodeGen (e.g., python -m your_codegen --apply)
  - FIXER_CMD: shell command to execute for Fixer (e.g., python -m your_fixer --apply)
  - If not set, the server runs a safe simulation for each action.
- Start the server: python app.py
- Open http://localhost:5000

API:
- POST /api/run { action: "codegen" | "fixer" }
- GET /api/status/<task_id>
- POST /api/cancel/<task_id>
- GET /api/stream/<task_id> (Server-Sent Events)

