# Citation Extraction and Provenance Linking (Flask)

A lightweight Flask service to extract citations from research outputs and link them to external provenance sources (Crossref).

Features:
- Extracts citations from a References/Bibliography section using heuristics
- Detects DOI and URLs within references
- Resolves citations against Crossref by DOI or bibliographic search
- Simple web UI and HTTP API

Endpoints:
- GET / — minimal UI for manual testing
- GET /api/health — health check
- POST /api/extract-citations — body: { text?, url? } or multipart file upload; returns extracted citations
- POST /api/link-provenance — body: { citations: [...] }; enriches with provenance
- POST /api/process — body: { text?, url?, link_provenance?: boolean } or multipart file; extract and optionally link

Quick start:
1. python -m venv .venv && source .venv/bin/activate
2. pip install -r requirements.txt
3. FLASK_DEBUG=1 python app.py
4. Open http://localhost:5000

Notes:
- Crossref API is used for provenance linking; network access is required.
- PDF text extraction uses pdfminer.six; quality depends on PDF structure.
- The citation parser is heuristic and may not cover all styles.

