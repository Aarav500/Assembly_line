Auto-refinement loop: agent runs, measures results, tunes prompts and re-runs

How it works
- Create a run with an initial prompt and a list of criteria to satisfy.
- The agent generates an output.
- The evaluator measures how many criteria are satisfied (simple string containment).
- The tuner refines the prompt with feedback for missing criteria.
- Repeat until target_score is reached or max_iterations is hit.

Run server
- pip install -r requirements.txt
- export OPENAI_API_KEY=... (optional; defaults to dummy model)
- python app.py

API
- POST /runs
  Body: {
    "initial_prompt": "...",
    "criteria": ["must mention X", "include a summary"],
    "target_score": 0.9,
    "max_iterations": 5,
    "model": "dummy" | "openai:gpt-4o-mini",
    "temperature": 0.2
  }

- GET /runs
- GET /runs/{id}
- POST /runs/{id}/step
- POST /runs/{id}/auto
- POST /runs/{id}/stop
- POST /runs/{id}/reset

Example curl
curl -s -X POST http://localhost:5000/runs \
  -H 'Content-Type: application/json' \
  -d '{
    "initial_prompt": "Write a short product description for a new eco-friendly water bottle.",
    "criteria": ["mention eco-friendly", "include capacity in ounces", "include a call to action"],
    "target_score": 1.0,
    "max_iterations": 3,
    "model": "dummy"
  }' | jq . > run.json

RUN_ID=$(jq -r .id run.json)

# Single step
curl -s -X POST http://localhost:5000/runs/$RUN_ID/step | jq .

# Or auto until done
curl -s -X POST http://localhost:5000/runs/$RUN_ID/auto | jq .

