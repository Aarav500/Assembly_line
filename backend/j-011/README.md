Playgrounds for trying out endpoints and models (mocked)

Stack: Python + Flask

Features
- Mocked model catalog (/api/models)
- Text generation (/api/generate) with optional Server-Sent Events style streaming
- Chat completions (/api/chat) with streaming
- Embeddings (/api/embeddings) deterministic, hash-based vectors
- Simple web UI to experiment with all endpoints

Quickstart
1. Create a virtual environment and install dependencies:
   python -m venv .venv
   . .venv/bin/activate  # on Windows: .venv\\Scripts\\activate
   pip install -r requirements.txt

2. Run the server:
   python app.py

3. Open the playground:
   http://localhost:5000

Notes
- All responses are mocked and generated locally; no external API calls.
- Streaming uses a POST with text/event-stream (SSE-like). The included frontend parses the stream manually.
- Token counts and latencies are heuristic and for demo purposes only.

