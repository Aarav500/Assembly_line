Planning Agent - Stepwise Manifests and Checklists (Flask)

Overview
- A lightweight planning agent service that generates stepwise manifests and checklists before execution.
- Supports plan creation, approval, checklist updates, and controlled execution.

Endpoints
- GET /api/health: Service health.
- POST /api/plan: Create a plan.
  - Body: { goal: string, context?: string, constraints?: string[], preferences?: object }
- GET /api/plan/<plan_id>: Fetch plan and manifest.
- POST /api/plan/<plan_id>/approve: Approve a plan for execution.
- POST /api/plan/<plan_id>/checklist: Update checklist items.
  - Body: { updates: [{ step_id: string, updates: [{ item_id: string, done: boolean }] }] }
- POST /api/plan/<plan_id>/execute: Execute plan (sequential or stepwise)
  - Body: { stepwise?: boolean }
- GET /api/plan/<plan_id>/status: Execution status and logs.

Quickstart
1) Install dependencies
   pip install -r requirements.txt

2) Run
   python app.py

3) Example curl
   Create plan:
   curl -s -X POST http://localhost:8000/api/plan \
     -H 'Content-Type: application/json' \
     -d '{"goal":"Build a Flask service that plans work","context":"Internal tool","constraints":["No external APIs"],"preferences":{}}'

   Approve:
   curl -s -X POST http://localhost:8000/api/plan/<plan_id>/approve

   Update checklist (first step items):
   curl -s -X POST http://localhost:8000/api/plan/<plan_id>/checklist \
     -H 'Content-Type: application/json' \
     -d '{"updates":[{"step_id":"<step_id>","updates":[{"item_id":"<item_id>","done":true}]}]}'

   Execute step-by-step:
   curl -s -X POST http://localhost:8000/api/plan/<plan_id>/execute -H 'Content-Type: application/json' -d '{"stepwise":true}'

Notes
- This service performs deterministic planning (no external LLM calls).
- Execution is simulated and enforces that mandatory checklist items are completed before each step.

