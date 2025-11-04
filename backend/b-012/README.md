One-Click Literature Review

Stack: Python, Flask

Features
- Searches Crossref, arXiv, and PubMed (no API keys required; optional email for PubMed politeness)
- Generates a research brief with: overview summary, themes/keywords, key papers, methods, datasets, gaps/open questions, and formatted references
- Simple web UI for one-click generation

Quickstart
1. Python 3.10+
2. pip install -r requirements.txt
3. export FLASK_APP=app.py
4. flask run
5. Open http://localhost:5000

Configuration
- PUBMED_EMAIL: Optional environment variable to pass an email to NCBI E-utilities.

Notes
- Summarization is heuristic/extractive (frequency-based sentence ranking). No external LLM required.
- API rate limits may apply; reduce max results or increase years back if needed.

