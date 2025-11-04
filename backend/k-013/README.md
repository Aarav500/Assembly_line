Cost-aware routing (Flask)

Overview
- A small Flask service that selects an LLM model based on cost/quality/latency constraints, then generates a response through the chosen provider.
- Default provider is a mock provider so the service runs without API keys. Optionally enable OpenAI via environment variables.

Endpoints
- GET /health: Service health.
- GET /models: List registered models and pricing metadata.
- POST /route: Select a model and generate a response.

POST /route request body
{
  "input": "Write a haiku about the sea.",
  "constraints": {
    "max_cost_usd": 0.002,
    "min_quality": 3,
    "max_latency_ms": 1000,
    "prefer_provider": "mock"
  },
  "metadata": {
    "task_type": "summarization",
    "expected_output_tokens": 128
  }
}

Response
{
  "model": "mock:advanced",
  "strategy": "quality_then_cost_with_provider_bias",
  "decision_trace": ["..."],
  "estimate": {"input_tokens": 12, "output_tokens": 128, "cost_usd": 0.00082, "latency_ms": 500},
  "response": "[MOCK:advanced] Echo: Write a haiku about the sea.",
  "provider_latency_ms": 500
}

Model selection logic
- Estimate input and expected output tokens.
- Filter candidates by latency if provided.
- Prefer models meeting the required quality (derived from constraints or task_type) and, if provided, the cost budget.
- If none fit both, fallback to quality-only, then cost-only, then the absolute cheapest.
- Optional prefer_provider introduces a slight tie-break bias.

Configuration
- MODELS_CONFIG_JSON: JSON array to fully override model registry. Format: [[provider, name, quality, in_cost_per_1k, out_cost_per_1k, latency_ms, max_output_tokens], ...]
- OpenAI (optional):
  - OPENAI_API_KEY: required to use OpenAI provider
  - OPENAI_MODEL_NAME: e.g. "gpt-4o-mini"
  - OPENAI_INPUT_COST_PER_1K, OPENAI_OUTPUT_COST_PER_1K
  - OPENAI_MODEL_QUALITY (1-5), OPENAI_MODEL_LATENCY_MS, OPENAI_MODEL_MAX_TOKENS

Run locally
- pip install -r requirements.txt
- export FLASK_APP=app.py
- flask run --port 8000

Examples
curl -s localhost:8000/route -X POST -H 'Content-Type: application/json' -d '{"input":"Explain recursion to a child.","constraints":{"min_quality":3,"max_cost_usd":0.005},"metadata":{"task_type":"qa"}}' | jq .

Notes
- Token, quality, and latency are heuristic estimates intended for routing, not billing.
- The mock provider does not call external APIs.

