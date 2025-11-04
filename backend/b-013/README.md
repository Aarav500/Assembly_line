Full Research Paper Generator (structured with citations & LaTeX export)

Stack: Python, Flask

Features:
- Generates a structured paper: Abstract, Introduction, Related Work, Methods, Experiments, Results, Discussion, Conclusion.
- Auto-inserts inline citations and builds a references section.
- Accepts seed references as BibTeX or simple lines (Author; Title; Venue; Year).
- Exports to a self-contained LaTeX .tex file (no external .bib needed).
- Simple web UI and JSON API.

Quickstart:
1) Create a virtual environment and install requirements:
   python -m venv .venv
   . .venv/bin/activate  # Windows: .venv\\Scripts\\activate
   pip install -r requirements.txt

2) Run the app:
   python app.py

3) Open in your browser:
   http://localhost:5000

API:
POST /api/generate
Content-Type: application/json
{
  "topic": "Federated Learning for IoT",
  "title": "Optional title",
  "authors": "A. Researcher; B. Scientist",
  "keywords": "privacy, edge, optimization",
  "references_text": "@article{...}",
  "length": "short|medium|long",
  "citation_style": "numeric|author-year"
}

Response:
{
  "paper_id": "...",
  "paper": { ... structured paper ... }
}

Notes:
- The generator uses rule-based templates and locally fabricated references when not provided. For production, replace with a real content generator and a bibliographic lookup service.
- LaTeX output uses thebibliography environment and keeps inline numeric markers like [1] in text.

