from __future__ import annotations
from datetime import datetime
from typing import Any

from flask import Blueprint, current_app, jsonify, request

api_bp = Blueprint("api", __name__)


def _search():
    return current_app.extensions["search"]


@api_bp.get("/health")
def health():
    ok = False
    try:
        ok = _search().ping()
    except Exception:
        ok = False
    return jsonify({"status": "ok" if ok else "degraded"}), 200 if ok else 503


@api_bp.post("/indexes/<index>/init")
def init_index(index: str):
    res = _search().create_index(index)
    return jsonify(res)


@api_bp.delete("/indexes/<index>")
def delete_index(index: str):
    res = _search().delete_index(index)
    return jsonify(res)


@api_bp.post("/indexes/<index>/documents")
def add_document(index: str):
    data = request.get_json(force=True, silent=False) or {}
    doc_id = data.get("id")
    if doc_id is None:
        return jsonify({"error": "id is required"}), 400
    # Normalize created_at
    created_at = data.get("created_at")
    if isinstance(created_at, (int, float)):
        # epoch seconds
        data["created_at"] = datetime.utcfromtimestamp(float(created_at)).isoformat()
    elif isinstance(created_at, str):
        try:
            # accept as-is if parseable
            datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except Exception:
            data["created_at"] = datetime.utcnow().isoformat()
    else:
        data["created_at"] = datetime.utcnow().isoformat()

    res = _search().index_document(index=index, id=doc_id, body=data)
    return jsonify(res), 202 if current_app.config.get("SEARCH_BACKEND") == "meilisearch" else 200


@api_bp.get("/indexes/<index>/documents/<doc_id>")
def get_document(index: str, doc_id: str):
    doc = _search().get_document(index=index, id=doc_id)
    if not doc:
        return jsonify({"error": "not_found"}), 404
    return jsonify(doc)


@api_bp.post("/indexes/<index>/bulk")
def bulk(index: str):
    payload = request.get_json(force=True, silent=False)
    if not isinstance(payload, list):
        return jsonify({"error": "Expected a JSON array of documents"}), 400
    # normalize created_at
    normalized = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        doc = dict(item)
        if doc.get("created_at") is None:
            doc["created_at"] = datetime.utcnow().isoformat()
        normalized.append(doc)
    res = _search().bulk_index(index=index, docs=normalized)
    return jsonify(res), 202 if current_app.config.get("SEARCH_BACKEND") == "meilisearch" else 200


@api_bp.get("/indexes/<index>/search")
def search(index: str):
    q = request.args.get("q") or ""
    try:
        limit = int(request.args.get("limit", 10))
        offset = int(request.args.get("offset", 0))
    except Exception:
        return jsonify({"error": "limit and offset must be integers"}), 400

    res = _search().search(index=index, query=q, limit=limit, offset=offset)
    return jsonify(res)

