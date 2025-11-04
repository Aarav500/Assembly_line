RAG Prompt Builder (Flask)

Overview
- Simple RAG-style prompt builder that automatically retrieves the top-K relevant chunks using a TF-IDF retriever and returns a ready-to-use prompt.

Key Features
- Index text files in the data/ directory with configurable chunk size and overlap.
- Retrieve top-K relevant chunks for a query.
- Build a RAG prompt that includes context chunks and optional citations.
- REST API with endpoints for prompt generation, indexing, and stats.

Project Structure
- app.py: Flask server with endpoints
- rag/indexer.py: Data loading, chunking, TF-IDF index building and persistence
- rag/retriever.py: Similarity search (top-K by cosine similarity)
- rag/prompt_builder.py: Prompt construction from retrieved chunks
- data/: Sample documents
- storage/: Saved index (auto-created)

Endpoints
- GET /health -> {"status":"ok"}
- GET /stats -> basic index information
- POST /reindex -> rebuild index with JSON body: {"chunk_size": 180, "chunk_overlap": 40}
- POST /prompt -> build prompt
  Body example:
  {
    "query": "What is retrieval augmented generation?",
    "k": 5,
    "instructions": "You are a helpful assistant.",
    "answer_guidelines": "Be concise.",
    "include_citations": true
  }

Quick Start
1) Create and activate a virtual environment.
2) pip install -r requirements.txt
3) Optionally, add .txt files to the data/ directory.
4) python app.py
5) POST to http://localhost:5000/prompt with a JSON body containing your query.

Environment Variables (optional)
- DATA_DIR: directory of source .txt files (default: data)
- INDEX_STORAGE_DIR: directory for the persisted index (default: storage)
- CHUNK_SIZE: chunk size in tokens/words (default: 180)
- CHUNK_OVERLAP: overlap in tokens/words (default: 40)
- PORT: server port (default: 5000)

Notes
- This demo uses TF-IDF for retrieval to avoid external dependencies or API keys. You can replace it with embedding-based retrieval if preferred.

