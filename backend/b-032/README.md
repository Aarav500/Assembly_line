Minimal Business Plan and Pitch Deck Generator

Stack: Python + Flask

Features
- Input your startup basics and auto-generate a concise business plan
- One-click download of a minimal pitch deck (.pptx)

Quickstart
1. Create virtual environment and install deps:
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
   pip install -r requirements.txt

2. Run the app:
   export FLASK_APP=app.py
   export FLASK_ENV=development
   python app.py

3. Open http://localhost:5000

Notes
- PPTX generation uses python-pptx with the default template.
- To try a preset example, click "Use Example Data" on the home page.
- Downloads are stored in session; ensure SECRET_KEY is set in production.

