import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify, url_for
from typing import Optional
from werkzeug.exceptions import NotFound, BadRequest

from config import DEFAULT_CHUNK_SIZE, MAX_CHUNK_SIZE, WORKER_THREADS, RESULTS_PAGE_SIZE
from batch import (
    InMemoryStore,
    WorkerPool,
    BatchStatus,
    ChunkStatus,
    create_batch_from_items,
    batch_results,
    retry_failed_items,
)

app = Flask(__name__)
store = InMemoryStore()
workers = WorkerPool(store=store, worker_count=WORKER_THREADS)
workers.start()


def get_batch_or_404(batch_id: str):
    batch = store.get_batch(batch_id)
    if not batch:
        raise NotFound(description=f"Batch {batch_id} not found")
    return batch


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/batches", methods=["POST"])
def create_batch():
    if not request.is_json:
        raise BadRequest(description="Content type must be application/json")
    payload = request.get_json(silent=True) or {}
    items = payload.get("items")
    if not isinstance(items, list) or len(items) == 0:
        raise BadRequest(description="Field 'items' must be a non-empty array")
    chunk_size = int(payload.get("chunk_size", DEFAULT_CHUNK_SIZE))
    if chunk_size < 1 or chunk_size > MAX_CHUNK_SIZE:
        raise BadRequest(description=f"chunk_size must be between 1 and {MAX_CHUNK_SIZE}")
    operation = payload.get("operation", "echo")
    metadata = payload.get("metadata", {})

    batch = create_batch_from_items(items, chunk_size, operation, metadata)
    store.create_batch(batch)

    response = {
        "id": batch.id,
        "status": batch.status,
        "created_at": batch.created_at,
        "total_items": batch.total_items,
        "chunk_size": batch.chunk_size,
        "links": {
            "self": url_for("get_batch", batch_id=batch.id, _external=True),
            "start": url_for("start_batch", batch_id=batch.id, _external=True),
            "results": url_for("get_batch_results", batch_id=batch.id, _external=True),
            "chunks": url_for("list_chunks", batch_id=batch.id, _external=True),
        },
    }
    return jsonify(response), 201


@app.route("/batches/<batch_id>/start", methods=["POST"])
def start_batch(batch_id: str):
    batch = get_batch_or_404(batch_id)
    # Enqueue all pending chunks
    with store.with_lock():
        for ch in batch.chunks:
            if ch.status == ChunkStatus.PENDING:
                workers.submit_chunk(batch_id, ch.id)
    return jsonify({"message": "Batch started", "id": batch.id, "status": batch.status})


@app.route("/batches/<batch_id>", methods=["GET"])
def get_batch(batch_id: str):
    batch = get_batch_or_404(batch_id)
    return jsonify(batch.to_summary())


@app.route("/batches/<batch_id>/results", methods=["GET"])
def get_batch_results(batch_id: str):
    batch = get_batch_or_404(batch_id)
    status = request.args.get("status")  # success | failed | cancelled
    if status and status not in ("success", "failed", "cancelled"):
        raise BadRequest(description="Invalid status filter")
    try:
        offset = int(request.args.get("offset", 0))
        limit = int(request.args.get("limit", RESULTS_PAGE_SIZE))
    except Exception:
        raise BadRequest(description="offset and limit must be integers")
    if offset < 0 or limit < 1 or limit > 10000:
        raise BadRequest(description="Invalid pagination parameters")
    with store.with_lock():
        data = batch_results(batch, status=status, offset=offset, limit=limit)
    return jsonify(data)


@app.route("/batches/<batch_id>/chunks", methods=["GET"])
def list_chunks(batch_id: str):
    batch = get_batch_or_404(batch_id)
    with store.with_lock():
        chunks = [c.to_summary() for c in batch.chunks]
    return jsonify({"batch_id": batch.id, "chunks": chunks})


@app.route("/batches/<batch_id>/chunks/<chunk_id>", methods=["GET"])
def get_chunk(batch_id: str, chunk_id: str):
    batch = get_batch_or_404(batch_id)
    include_results = request.args.get("include_results", "false").lower() == "true"
    with store.with_lock():
        ch = next((c for c in batch.chunks if c.id == chunk_id), None)
        if not ch:
            raise NotFound(description=f"Chunk {chunk_id} not found")
        out = ch.to_summary()
        if include_results:
            out["results"] = [
                {
                    "item_id": r.item_id,
                    "status": r.status,
                    "input": r.input,
                    "output": r.output,
                    "error": r.error,
                }
                for r in ch.results
            ]
    return jsonify(out)


@app.route("/batches/<batch_id>/cancel", methods=["POST"])
def cancel_batch(batch_id: str):
    batch = get_batch_or_404(batch_id)
    with store.with_lock():
        batch.cancel_flag = True
    return jsonify({"message": "Cancellation requested", "id": batch.id})


@app.route("/batches/<batch_id>/retry", methods=["POST"])
def retry_batch(batch_id: str):
    batch = get_batch_or_404(batch_id)
    with store.with_lock():
        new_chunk_ids = retry_failed_items(batch)
        if not new_chunk_ids:
            return jsonify({"message": "No failed/cancelled items to retry", "id": batch.id, "created_chunks": 0}), 200
        # clear cancel flag for retry
        batch.cancel_flag = False
        # don't reset counters; retries contribute additional processed items & successes/failures
        # enqueue new chunks
        for ch_id in new_chunk_ids:
            workers.submit_chunk(batch_id, ch_id)
    return jsonify({"message": "Retry scheduled", "id": batch.id, "created_chunks": len(new_chunk_ids)})


@app.errorhandler(BadRequest)
def handle_bad_request(e):
    return jsonify({"error": "bad_request", "message": e.description}), 400


@app.errorhandler(NotFound)
def handle_not_found(e):
    return jsonify({"error": "not_found", "message": e.description}), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)



def create_app():
    return app
