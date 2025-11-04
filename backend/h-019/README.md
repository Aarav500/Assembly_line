Natural-language query interface to project knowledge

Stack: Python, Flask

Features
- Indexes your project files (code, docs, configs) into a TF-IDF search index
- Ask natural-language questions like "How does auth work?"
- Returns extractive answer synthesized from top-matching snippets
- Shows sources with file paths and line ranges

Quick start
1) Install deps
   pip install -r requirements.txt

2) Run server
   export PROJECT_DIR=path/to/your/project   # optional, defaults to current directory
   export INDEX_DIR=index_data               # optional
   python app.py

3) Build index
   - The server will try to auto-index PROJECT_DIR on first run.
   - Or trigger manually at http://localhost:8000 and click "Rebuild Index".
   - Or curl:
     curl -X POST http://localhost:8000/build_index -H 'Content-Type: application/json' -d '{"root_dir": "/abs/path"}'

4) Ask questions
   - Open http://localhost:8000
   - Or via API:
     curl -X POST http://localhost:8000/query -H 'Content-Type: application/json' -d '{"question":"How does auth work?","top_k":5}'

API
- GET /health -> { status, has_index, index_dir }
- POST /build_index { root_dir?: string, include?: string[], exclude?: string[] } -> { ok, stats }
- POST /query { question: string, top_k?: number } -> { ok, answer, matches: [{ file, start_line, end_line, score, snippet }] }

Notes
- By default, indexes common text/code extensions and skips typical vendor/venv artifacts.
- Chunking is line-based (40 lines, 10 line overlap) to keep snippets coherent.
- Retrieval uses cosine similarity over TF-IDF; answer is extractive (top sentences).
- No external LLM/API required.

Customize
- Adjust allowed extensions, excludes, chunk sizes in indexer.py
- Enhance answer composition or integrate an LLM if desired.

