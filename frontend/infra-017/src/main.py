from typing import List, Optional
from fastapi import FastAPI, Query, Body
from fastapi.responses import JSONResponse
from datetime import datetime

from .config import get_es_client, INDEX_NAME
from .index_manager import create_index, delete_index, reset_index, upsert_document, bulk_index, reload_search_analyzers
from .models import Document
from .search import search as es_search, autocomplete as es_autocomplete

app = FastAPI(title="Search Service (Elasticsearch)", version="1.0.0")

@app.on_event("startup")
def on_startup():
    es = get_es_client()
    create_index(es, INDEX_NAME)

@app.get("/health")
def health():
    es = get_es_client()
    info = es.info()
    return {"name": info.get("name"), "cluster_name": info.get("cluster_name"), "version": info.get("version", {}).get("number")}

@app.post("/index/reset")
def api_reset_index():
    es = get_es_client()
    return reset_index(es, INDEX_NAME)

@app.post("/synonyms/reload")
def api_reload_synonyms():
    es = get_es_client()
    return reload_search_analyzers(es, INDEX_NAME)

@app.post("/document")
def api_upsert_document(doc: Document):
    es = get_es_client()
    payload = doc.model_dump(exclude_none=True)
    # Ensure created_at
    if "created_at" not in payload:
        payload["created_at"] = datetime.utcnow().isoformat()
    doc_id = payload.pop("id", None)
    return upsert_document(es, INDEX_NAME, doc_id, payload)

@app.post("/documents/bulk")
def api_bulk_documents(docs: List[Document]):
    es = get_es_client()
    payloads = []
    for d in docs:
        m = d.model_dump(exclude_none=True)
        if "created_at" not in m:
            m["created_at"] = datetime.utcnow().isoformat()
        payloads.append(m)
    return bulk_index(es, INDEX_NAME, payloads)

@app.get("/search")
def api_search(
    q: Optional[str] = Query(default=None, description="Full-text query"),
    category: Optional[List[str]] = Query(default=None),
    brand: Optional[List[str]] = Query(default=None),
    tags: Optional[List[str]] = Query(default=None),
    price_min: Optional[float] = Query(default=None),
    price_max: Optional[float] = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
    sort: Optional[str] = Query(default=None, description="price_asc|price_desc|newest|score"),
    fields: Optional[List[str]] = Query(default=None)
):
    es = get_es_client()
    filters = {
        "category": category,
        "brand": brand,
        "tags": tags,
        "price_min": price_min,
        "price_max": price_max,
    }
    resp = es_search(es, INDEX_NAME, q, filters, page=page, size=size, sort=sort, fields=fields)
    return JSONResponse(resp)

@app.get("/autocomplete")
def api_autocomplete(prefix: str = Query(..., min_length=1), size: int = Query(8, ge=1, le=20)):
    es = get_es_client()
    resp = es_autocomplete(es, INDEX_NAME, prefix, size=size)
    return JSONResponse(resp)

