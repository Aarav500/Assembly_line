import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import uuid
from flask import Flask, request, jsonify
from dotenv import load_dotenv

from config import AppConfig
from services.embedding import EmbeddingService
from stores.chroma_store import ChromaVectorStore
from stores.pgvector_store import PGVectorStore

load_dotenv()

app = Flask(__name__)
config = AppConfig()

# Initialize embedding service (loads local model)
embedding_service = EmbeddingService(
    model_name=config.EMBEDDING_MODEL_NAME,
    device=config.EMBEDDING_DEVICE,
    normalize_default=True,
)

# Initialize vector stores lazily; create on demand
chroma_store = None
pg_store = None

if "chroma" in config.AVAILABLE_STORES:
    try:
        chroma_store = ChromaVectorStore(
            persist_directory=config.CHROMA_PERSIST_DIR,
            metric="cosine",
        )
    except Exception as e:
        app.logger.warning(f"Chroma init failed: {e}")

if "pgvector" in config.AVAILABLE_STORES:
    try:
        pg_store = PGVectorStore(
            host=config.PG_HOST,
            port=config.PG_PORT,
            database=config.PG_DATABASE,
            user=config.PG_USER,
            password=config.PG_PASSWORD,
            schema=config.PG_SCHEMA,
            default_index_lists=config.PG_INDEX_LISTS,
            use_extension=config.PG_CREATE_EXTENSION,
            distance_metric="cosine",
            embedding_dim=embedding_service.dimension,
        )
    except Exception as e:
        app.logger.warning(f"pgvector init failed: {e}")


def _get_store(store_name: str):
    name = (store_name or config.DEFAULT_STORE).lower()
    if name == "chroma":
        if chroma_store is None:
            raise RuntimeError("Chroma store is not available")
        return chroma_store, "chroma"
    if name == "pgvector":
        if pg_store is None:
            raise RuntimeError("pgvector store is not available")
        return pg_store, "pgvector"
    raise ValueError(f"Unsupported store: {store_name}")


@app.route("/health", methods=["GET"]) 
def health():
    return jsonify({
        "status": "ok",
        "model": embedding_service.model_name,
        "dim": embedding_service.dimension,
        "default_store": config.DEFAULT_STORE,
        "available_stores": config.AVAILABLE_STORES,
    })


@app.route("/embed", methods=["POST"]) 
def embed():
    data = request.get_json(force=True, silent=True) or {}
    texts = data.get("texts") or data.get("text")
    if texts is None:
        return jsonify({"error": "Missing 'texts' (list[str]) or 'text' (str) in body"}), 400
    if isinstance(texts, str):
        texts = [texts]
    if not isinstance(texts, list) or not all(isinstance(t, str) for t in texts):
        return jsonify({"error": "'texts' must be a list of strings"}), 400

    normalize = data.get("normalize")
    embeddings = embedding_service.embed(texts, normalize=normalize)
    return jsonify({
        "model": embedding_service.model_name,
        "dim": embedding_service.dimension,
        "count": len(embeddings),
        "embeddings": embeddings,
    })


@app.route("/upsert", methods=["POST"]) 
def upsert():
    data = request.get_json(force=True, silent=True) or {}
    store_req = data.get("store")
    collection = data.get("collection") or data.get("namespace") or config.DEFAULT_COLLECTION
    documents = data.get("documents")

    if not isinstance(documents, list) or len(documents) == 0:
        return jsonify({"error": "'documents' must be a non-empty list of {id?, text, metadata?}"}), 400

    try:
        store, store_name = _get_store(store_req)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    # Prepare payload
    ids = []
    texts = []
    metadatas = []
    for doc in documents:
        if not isinstance(doc, dict) or "text" not in doc:
            return jsonify({"error": "Each document must be an object with at least 'text' field"}), 400
        did = doc.get("id") or str(uuid.uuid4())
        ids.append(did)
        texts.append(doc["text"])
        md = doc.get("metadata")
        if md is not None and not isinstance(md, dict):
            return jsonify({"error": "'metadata' must be an object if provided"}), 400
        metadatas.append(md or {})

    # Embed locally
    embeddings = embedding_service.embed(texts, normalize=True)

    try:
        upserted = store.upsert(
            collection=collection,
            ids=ids,
            texts=texts,
            metadatas=metadatas,
            embeddings=embeddings,
            embedding_dim=embedding_service.dimension,
        )
    except Exception as e:
        return jsonify({"error": f"Upsert failed: {e}"}), 500

    return jsonify({
        "store": store_name,
        "collection": collection,
        "upserted": upserted,
    })


@app.route("/query", methods=["POST"]) 
def query():
    data = request.get_json(force=True, silent=True) or {}
    store_req = data.get("store")
    collection = data.get("collection") or data.get("namespace") or config.DEFAULT_COLLECTION
    query_text = data.get("query")
    top_k = int(data.get("top_k") or data.get("k") or 5)

    if not isinstance(query_text, str) or not query_text.strip():
        return jsonify({"error": "'query' must be a non-empty string"}), 400

    try:
        store, store_name = _get_store(store_req)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    # Embed query
    q_emb = embedding_service.embed([query_text], normalize=True)[0]

    try:
        results = store.query(collection=collection, query_embedding=q_emb, top_k=top_k)
    except Exception as e:
        return jsonify({"error": f"Query failed: {e}"}), 500

    return jsonify({
        "store": store_name,
        "collection": collection,
        "count": len(results),
        "results": results,
    })


@app.route("/reset", methods=["POST"]) 
def reset():
    data = request.get_json(force=True, silent=True) or {}
    store_req = data.get("store")
    collection = data.get("collection") or data.get("namespace") or config.DEFAULT_COLLECTION

    try:
        store, store_name = _get_store(store_req)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    try:
        store.reset_collection(collection)
    except Exception as e:
        return jsonify({"error": f"Reset failed: {e}"}), 500

    return jsonify({
        "store": store_name,
        "collection": collection,
        "reset": True,
    })


if __name__ == "__main__":
    app.run(host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8000")), debug=os.getenv("FLASK_DEBUG", "0") == "1")



def create_app():
    return app


@app.route('/add', methods=['POST'])
def _auto_stub_add():
    return 'Auto-generated stub for /add', 200


@app.route('/search', methods=['POST'])
def _auto_stub_search():
    return 'Auto-generated stub for /search', 200
