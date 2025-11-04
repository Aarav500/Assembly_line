Auto-batching & token-optimization middleware for downstream LLM calls

Features
- Auto-batching: Groups compatible requests within a short window (default 50ms) and sends a single downstream call using multi-item prompting. Responses are split back to individual requests.
- Token optimization: Heuristic prompt compression and budgeted truncation to fit model context windows while preserving important content.
- Caching: In-memory TTL LRU cache to avoid duplicate downstream calls.
- OpenAI-compatible endpoint: Minimal /v1/chat/completions implementation.

Quick start
1) Create .env from example and set OPENAI_API_KEY (or DOWNSTREAM_URL for a generic provider).
2) Install deps: pip install -r requirements.txt
3) Run: python run.py
4) Call the API:
   curl -s http://localhost:8080/v1/chat/completions \
     -H 'Content-Type: application/json' \
     -d '{"model":"gpt-4o-mini","messages":[{"role":"system","content":"You are helpful."},{"role":"user","content":"Say hello"}]}' | jq

Notes
- Batching groups requests by model, temperature, top_p, and system prompt. Only compatible requests are batched together.
- Multi-item batching uses strict XML-tagged answers (<answer id="...">...</answer>) to parse the combined response.
- If parsing fails for an item, the middleware falls back to an individual downstream call for that item.
- Token estimation is heuristic (chars/4). For production, integrate a tokenizer specific to your model for precise accounting.
- Streaming is not implemented in this example.

Environment variables
- DOWNSTREAM_PROVIDER: "openai" (default) or "generic".
- OPENAI_API_KEY, OPENAI_BASE_URL: for OpenAI.
- DOWNSTREAM_URL: for generic provider that accepts OpenAI-style chat/completions.
- BATCH_WINDOW_MS, MAX_BATCH_SIZE: batching controls.
- CACHE_TTL_SEC, CACHE_MAX_ENTRIES: cache controls.
- DEFAULT_MODEL, DEFAULT_MAX_OUTPUT_TOKENS, DEFAULT_TEMPERATURE, DEFAULT_TOP_P: model defaults.
- DEFAULT_CONTEXT_TOKENS, META_OVERHEAD_TOKENS: token budgets.
- REQUEST_TIMEOUT_SEC: request timeout.

Caveats
- The batching prompt design assumes the downstream model follows instructions and returns strictly formatted outputs. Some models may occasionally add extra text; parser will extract tagged answers.
- Best for single-turn or short multi-turn prompts; for complex multi-turn conversations, consider summarizing history upstream or enhance condense_messages_for_batch.

