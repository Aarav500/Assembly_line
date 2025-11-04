Batched repo generation (single LLM call → whole repo)

This project demonstrates generating an entire repository from a single LLM call. It provides a Flask web UI and API that:
- Sends a single prompt to an LLM with instructions to return a JSON object listing all files and their content.
- Parses the response and writes the files to a uniquely named folder.
- Offers a zip download and per-file browsing.

Features
- Single-shot, whole-repo generation.
- Fallback fake mode (no API key required) for demo purposes.
- Path sanitization, file count and size limits.

Quickstart
1) Install dependencies
   pip install -r requirements.txt

2) Configure environment
   cp .env.example .env
   # Edit .env and add your OPENAI_API_KEY (optional)

3) Run the app
   python app.py
   # Open http://localhost:5000

Environment variables
- OPENAI_API_KEY: Your OpenAI API key (optional; fake mode if absent)
- OPENAI_API_BASE: API base URL (default: https://api.openai.com/v1)
- OPENAI_MODEL: Model name (default: gpt-4o-mini)
- OPENAI_FORCE_JSON: Try to enforce JSON-only responses (default: true)
- OUTPUT_BASE: Base directory for generated repos (default: ./generated)
- MAX_FILES: Max number of files allowed from LLM (default: 200)
- MAX_TOTAL_BYTES: Max total bytes across all files (default: 5MB)
- PORT: Flask port (default: 5000)

API
POST /generate
Request JSON:
{
  "prompt": "Describe the repository you want",
  "repo_name": "my-awesome-repo",   # optional
  "model": "gpt-4o-mini",           # optional
  "fake": false                      # optional, force fake mode
}

Response JSON:
{
  "id": "...",
  "repo_name": "...",
  "dir": "generated/...",
  "zip_url": "/download/<id>.zip",
  "files": [ {"path": "...", "bytes": 123}, ... ]
}

GET /download/<id>.zip
Download the generated repository as a zip archive.

GET /repo/<id>/<path>
Fetch an individual file.

How it works
- The system prompt (prompts/system_prompt.txt) strictly instructs the LLM to output only JSON with a files array. This enables single-call, batched repo creation.
- The server validates and writes the files, then zips the repo.

Notes
- The server limits the number of files and total size for safety.
- For binary assets, the LLM is instructed to include placeholders.

License
MIT

