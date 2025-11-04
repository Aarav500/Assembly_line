One-line to MVP (Flask)

Local setup
- python -m venv .venv && source .venv/bin/activate
- pip install -r requirements.txt
- python app.py

Open http://localhost:5000 and try an example one-liner like:
"An AI assistant that turns startup ideas into full plans for founders"

API
POST /api/generate
Body: {"one_liner": "...", "tone": "professional|concise|pitchy"}

