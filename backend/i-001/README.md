Immutable Audit Trail of LLM Prompts & Responses (Summarized)

Stack: Python + Flask + SQLite

Quick start:
- pip install -r requirements.txt
- python app.py

API:
- POST /jobs {"name": "optional"}
- GET /jobs
- GET /jobs/{job_id}
- POST /jobs/{job_id}/entries {"prompt": "...", "response": "...", "metadata": {}}
- GET /jobs/{job_id}/entries
- POST /jobs/{job_id}/seal
- GET /jobs/{job_id}/verify

Notes:
- Only summaries and SHA-256 hashes of prompt/response are stored; full texts are not persisted.
- Each entry is immutably chained via prev_entry_hash and entry_hash.
- Jobs can be sealed once to fix a root hash for the entire chain.
- SQLite triggers enforce immutability (no deletes, restricted updates).
- Set AUDIT_DB_PATH env var to change database path.

