import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from flask import Flask, request, jsonify
from rag.indexer import CorpusIndex
from rag.retriever import Retriever
from rag.prompt_builder import build_rag_prompt

# Basic Flask app for RAG prompt building
app = Flask(__name__)

# Global objects (loaded on startup)
INDEX_STORAGE_DIR = os.environ.get("INDEX_STORAGE_DIR", "storage")
DATA_DIR = os.environ.get("DATA_DIR", "data")
DEFAULT_CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "180"))
DEFAULT_CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "40"))

corpus_index = CorpusIndex(
    data_dir=DATA_DIR,
    storage_dir=INDEX_STORAGE_DIR,
    chunk_size=DEFAULT_CHUNK_SIZE,
    chunk_overlap=DEFAULT_CHUNK_OVERLAP,
)

retriever = None


def ensure_index_loaded():
    global retriever
    if not corpus_index.has_index():
        # Build index if missing
        corpus_index.build_index()
    else:
        corpus_index.load_index()
    retriever = Retriever(corpus_index)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/stats", methods=["GET"])
def stats():
    ensure_index_loaded()
    info = corpus_index.index_info()
    return jsonify(info)


@app.route("/reindex", methods=["POST"])
def reindex():
    payload = request.get_json(silent=True) or {}
    chunk_size = int(payload.get("chunk_size", corpus_index.chunk_size))
    chunk_overlap = int(payload.get("chunk_overlap", corpus_index.chunk_overlap))

    corpus_index.chunk_size = chunk_size
    corpus_index.chunk_overlap = chunk_overlap

    corpus_index.build_index()
    ensure_index_loaded()

    return jsonify({
        "status": "ok",
        "message": "Index rebuilt",
        "config": {
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap
        },
        "stats": corpus_index.index_info()
    })


@app.route("/prompt", methods=["POST"])
def prompt():
    ensure_index_loaded()
    data = request.get_json(silent=True) or {}

    query = data.get("query", "").strip()
    if not query:
        return jsonify({"error": "Missing 'query'"}), 400

    k = int(data.get("k", 5))
    if k <= 0:
        return jsonify({"error": "Parameter 'k' must be > 0"}), 400

    namespace = data.get("namespace")  # Optional; not used in this simple implementation

    retrieved = retriever.top_k(query=query, k=k)

    prompt_text = build_rag_prompt(
        query=query,
        retrieved_chunks=retrieved,
        instructions=data.get("instructions"),
        answer_guidelines=data.get("answer_guidelines"),
        include_citations=bool(data.get("include_citations", True)),
    )

    # Prepare chunk metadata for response
    chunks_meta = []
    for r in retrieved:
        chunks_meta.append({
            "id": r.get("id"),
            "source": r.get("source"),
            "position": r.get("position"),
            "score": r.get("score")
        })

    return jsonify({
        "prompt": prompt_text,
        "query": query,
        "k": k,
        "chunks": chunks_meta,
    })


if __name__ == "__main__":
    # Ensure storage dir exists and index is available before run
    os.makedirs(INDEX_STORAGE_DIR, exist_ok=True)
    ensure_index_loaded()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))



def create_app():
    return app


@app.route('/documents', methods=['POST'])
def _auto_stub_documents():
    return 'Auto-generated stub for /documents', 200


@app.route('/query', methods=['POST'])
def _auto_stub_query():
    return 'Auto-generated stub for /query', 200
