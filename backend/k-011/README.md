Sandbox-only dry-run mode for agents to produce changes as proposals only

Quick start
- Install deps: pip install -r requirements.txt
- Run: python run.py

Env vars
- SANDBOX_DRY_RUN: true|false (default: true). When true, agent changes are only recorded as proposals and cannot be approved/applied.
- DATA_DIR: directory for JSON storage (default: ./data)

API
- GET /health
- GET /config
- GET /items
- GET /items/<id>
- POST /agents/changes
  Request:
  {
    "agent_id": "agent-123",
    "resource": "items",
    "id": "item-1",
    "desired": {"name": "New Name", "value": 42},
    "auto_apply": false
  }
  Behavior:
  - If SANDBOX_DRY_RUN=true: create proposal only, no state change
  - If SANDBOX_DRY_RUN=false and auto_apply=true: apply immediately and record as applied proposal
  - If SANDBOX_DRY_RUN=false and auto_apply=false: create proposal awaiting approval

- GET /proposals
- GET /proposals/<id>
- POST /proposals/<id>/approve
  - Approves and applies proposal (403 if SANDBOX_DRY_RUN=true)
- POST /proposals/<id>/reject

Notes
- Diff is computed only for keys present in desired payload (no automatic removals). To remove fields, explicitly set them to null and they will be set to null.
- Data persisted in DATA_DIR/items.json and DATA_DIR/proposals.json.

