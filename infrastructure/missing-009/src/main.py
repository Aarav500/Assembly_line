import os
import time
from typing import List, Optional, Any, Dict
from fastapi import FastAPI, Query, Body
from pydantic import BaseModel
from elasticsearch import Elasticsearch, helpers
from datetime import datetime, timedelta

from .es import get_client, ensure_connected
from .index_setup import init_all_indices

PRODUCTS_INDEX = os.getenv("PRODUCTS_INDEX", "products")
ANALYTICS_INDEX = os.getenv("ANALYTICS_INDEX", "search-analytics")

app = FastAPI(title="Search API with Elasticsearch", version="1.0.0")


class BulkIndexRequest(BaseModel):
    file_path: Optional[str] = None


class ClickEvent(BaseModel):
    doc_id: str
    query: Optional[str] = None
    position: Optional[int] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None


def _filters_to_es(filters: Dict[str, Any]):
    clauses = []
    if filters.get("brand"):
        brands = filters["brand"]
        if isinstance(brands, list):
            clauses.append({"terms": {"brand": [b.lower() for b in brands]}})
        else:
            clauses.append({"term": {"brand": str(brands).lower()}})
    if filters.get("category"):
        cats = filters["category"]
        if isinstance(cats, list):
            clauses.append({"terms": {"category": [c.lower() for c in cats]}})
        else:
            clauses.append({"term": {"category": str(cats).lower()}})
    if filters.get("available") is not None:
        clauses.append({"term": {"available": bool(filters["available"])} })
    price_min = filters.get("price_min")
    price_max = filters.get("price_max")
    if price_min is not None or price_max is not None:
        range_q = {}
        if price_min is not None:
            range_q["gte"] = float(price_min)
        if price_max is not None:
            range_q["lte"] = float(price_max)
        clauses.append({"range": {"price": range_q}})
    return clauses


def _sort_clause(sort: str):
    if sort == "price_asc":
        return [{"price": "asc"}]
    if sort == "price_desc":
        return [{"price": "desc"}]
    if sort == "newest":
        return [{"created_at": "desc"}]
    # relevance
    return ["_score"]


def _search_body(q: Optional[str], filters: Dict[str, Any], from_: int, size: int, sort: str) -> Dict[str, Any]:
    filter_clauses = _filters_to_es(filters)

    if q and q.strip():
        q = q.strip()
        should = [
            {
                "multi_match": {
                    "query": q,
                    "fields": [
                        "name^4",
                        "name.autocomplete^3",
                        "brand^2",
                        "category^2",
                        "description"
                    ],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                    "operator": "and"
                }
            },
            {"match_phrase": {"name": {"query": q, "boost": 10}}}
        ]
        if len(q) >= 2:
            should.append({"match_phrase_prefix": {"name": {"query": q, "boost": 5}}})

        query: Dict[str, Any] = {
            "bool": {
                "must": [],
                "filter": filter_clauses,
                "should": should,
                "minimum_should_match": 1
            }
        }
    else:
        query = {"bool": {"filter": filter_clauses, "must": [{"match_all": {}}]}}

    body: Dict[str, Any] = {
        "from": from_,
        "size": size,
        "track_total_hits": True,
        "query": {
            "function_score": {
                "query": query,
                "boost_mode": "multiply",
                "score_mode": "sum",
                "functions": [
                    {
                        "field_value_factor": {
                            "field": "popularity",
                            "factor": 1.2,
                            "modifier": "log1p",
                            "missing": 1
                        }
                    },
                    {
                        "gauss": {
                            "created_at": {"origin": "now", "scale": "30d", "offset": "7d", "decay": 0.5}
                        },
                        "weight": 2
                    }
                ]
            }
        },
        "aggs": {
            "brands": {"terms": {"field": "brand", "size": 20}},
            "categories": {"terms": {"field": "category", "size": 20}},
            "price_stats": {"stats": {"field": "price"}},
            "price_ranges": {
                "range": {
                    "field": "price",
                    "ranges": [
                        {"to": 50},
                        {"from": 50, "to": 100},
                        {"from": 100, "to": 250},
                        {"from": 250, "to": 500},
                        {"from": 500}
                    ]
                }
            }
        },
        "highlight": {
            "pre_tags": ["<em>"],
            "post_tags": ["</em>"],
            "fields": {
                "name": {},
                "description": {}
            }
        },
        "sort": _sort_clause(sort)
    }
    return body


@app.get("/health")
def health():
    info = ensure_connected()
    return {"name": info.get("name"), "cluster": info.get("cluster_name"), "version": info.get("version", {}).get("number")}


@app.post("/index/init")
def init_indices():
    es = get_client()
    init_all_indices(es, PRODUCTS_INDEX, ANALYTICS_INDEX)
    return {"status": "ok", "products_index": PRODUCTS_INDEX, "analytics_index": ANALYTICS_INDEX}


@app.post("/index/bulk")
def bulk_index(req: BulkIndexRequest):
    es = get_client()
    init_all_indices(es, PRODUCTS_INDEX, ANALYTICS_INDEX)

    file_path = req.file_path or os.path.join(os.path.dirname(__file__), "..", "data", "sample_products.jsonl")
    file_path = os.path.abspath(file_path)

    actions = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            doc = __import__("json").loads(line)
            # Ensure suggest field
            doc["name_suggest"] = doc.get("name")
            actions.append({
                "_op_type": "index",
                "_index": PRODUCTS_INDEX,
                "_id": doc.get("id"),
                "_source": doc
            })

    if actions:
        helpers.bulk(es, actions)
    es.indices.refresh(index=PRODUCTS_INDEX)
    return {"status": "ok", "indexed": len(actions)}


@app.get("/search")
def search(
    q: Optional[str] = Query(default=None, description="Search query"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
    brand: Optional[List[str]] = Query(default=None),
    category: Optional[List[str]] = Query(default=None),
    price_min: Optional[float] = Query(default=None),
    price_max: Optional[float] = Query(default=None),
    available: Optional[bool] = Query(default=None),
    sort: str = Query(default="relevance", pattern="^(relevance|price_asc|price_desc|newest)$"),
    user_id: Optional[str] = Query(default=None),
    session_id: Optional[str] = Query(default=None),
):
    es = get_client()

    from_ = (page - 1) * size
    filters = {
        "brand": brand,
        "category": category,
        "price_min": price_min,
        "price_max": price_max,
        "available": available
    }

    body = _search_body(q, filters, from_, size, sort)

    t0 = time.time()
    res = es.search(index=PRODUCTS_INDEX, body=body)
    t1 = time.time()

    # Log analytics (non-blocking)
    try:
        es.index(index=ANALYTICS_INDEX, document={
            "event_type": "query",
            "timestamp": datetime.utcnow().isoformat(),
            "query": q or "",
            "filters": {k: v for k, v in filters.items() if v is not None},
            "total_hits": res.get("hits", {}).get("total", {}).get("value", 0),
            "took": res.get("took", int((t1 - t0) * 1000)),
            "index": PRODUCTS_INDEX,
            "user_id": user_id,
            "session_id": session_id
        })
    except Exception:
        pass

    hits = res.get("hits", {}).get("hits", [])
    results = []
    for h in hits:
        src = h.get("_source", {})
        item = {
            "id": h.get("_id"),
            "score": h.get("_score"),
            "name": src.get("name"),
            "description": src.get("description"),
            "brand": src.get("brand"),
            "category": src.get("category"),
            "price": src.get("price"),
            "available": src.get("available"),
            "popularity": src.get("popularity"),
            "created_at": src.get("created_at"),
            "highlights": h.get("highlight", {})
        }
        results.append(item)

    aggs = res.get("aggregations", {})
    return {
        "total": res.get("hits", {}).get("total", {}).get("value", 0),
        "took": res.get("took", 0),
        "page": page,
        "size": size,
        "results": results,
        "facets": {
            "brands": [{"key": b.get("key"), "count": b.get("doc_count")} for b in aggs.get("brands", {}).get("buckets", [])],
            "categories": [{"key": c.get("key"), "count": c.get("doc_count")} for c in aggs.get("categories", {}).get("buckets", [])],
            "price": {
                "stats": aggs.get("price_stats", {}),
                "ranges": [{"key": r.get("key"), "count": r.get("doc_count")} for r in aggs.get("price_ranges", {}).get("buckets", [])]
            }
        }
    }


@app.get("/suggest")
def suggest(prefix: str = Query(..., min_length=1), size: int = Query(5, ge=1, le=20), brand: Optional[str] = None, category: Optional[str] = None):
    es = get_client()

    contexts = {}
    if brand:
        contexts["brand"] = brand.lower()
    if category:
        contexts["category"] = category.lower()

    suggest_body: Dict[str, Any] = {
        "suggest": {
            "name-suggest": {
                "prefix": prefix,
                "completion": {
                    "field": "name_suggest",
                    "size": size,
                    "skip_duplicates": True,
                    **({"contexts": contexts} if contexts else {})
                }
            },
            "did_you_mean": {
                "text": prefix,
                "term": {
                    "field": "name",
                    "suggest_mode": "popular",
                    "min_word_length": 3
                }
            }
        },
        "_source": False
    }

    res = es.search(index=PRODUCTS_INDEX, body=suggest_body)

    comp = res.get("suggest", {}).get("name-suggest", [])
    term = res.get("suggest", {}).get("did_you_mean", [])

    completions = []
    for s in comp:
        for opt in s.get("options", []):
            completions.append({
                "text": opt.get("text"),
                "score": opt.get("_score", opt.get("score"))
            })

    did_you_mean = []
    for s in term:
        for opt in s.get("options", []):
            did_you_mean.append(opt.get("text"))

    return {
        "prefix": prefix,
        "completions": completions,
        "did_you_mean": did_you_mean
    }


@app.post("/analytics/click")
def log_click(event: ClickEvent):
    es = get_client()
    doc = event.model_dump()
    doc.update({
        "event_type": "click",
        "timestamp": datetime.utcnow().isoformat(),
        "index": PRODUCTS_INDEX
    })
    es.index(index=ANALYTICS_INDEX, document=doc)
    return {"status": "ok"}


@app.get("/analytics/top-queries")
def top_queries(days: int = Query(7, ge=1, le=90), size: int = Query(10, ge=1, le=100)):
    es = get_client()
    gte = (datetime.utcnow() - timedelta(days=days)).isoformat()

    body = {
        "size": 0,
        "query": {
            "range": {"timestamp": {"gte": gte}}
        },
        "aggs": {
            "queries": {
                "terms": {"field": "query.keyword", "size": size, "min_doc_count": 1},
                "aggs": {
                    "query_events": {"filter": {"term": {"event_type": "query"}}},
                    "click_events": {"filter": {"term": {"event_type": "click"}}},
                    "ctr": {
                        "bucket_script": {
                            "buckets_path": {
                                "clicks": "click_events._count",
                                "impressions": "query_events._count"
                            },
                            "script": "params.impressions > 0 ? params.clicks / params.impressions : 0"
                        }
                    }
                }
            }
        }
    }

    res = es.search(index=ANALYTICS_INDEX, body=body)
    buckets = res.get("aggregations", {}).get("queries", {}).get("buckets", [])

    items = []
    for b in buckets:
        items.append({
            "query": b.get("key"),
            "impressions": b.get("query_events", {}).get("doc_count", 0),
            "clicks": b.get("click_events", {}).get("doc_count", 0),
            "ctr": b.get("ctr", {}).get("value", 0)
        })

    return {"range_days": days, "top": items}


@app.get("/analytics/top-products")
def top_products(days: int = Query(7, ge=1, le=90), size: int = Query(10, ge=1, le=100)):
    es = get_client()
    gte = (datetime.utcnow() - timedelta(days=days)).isoformat()

    body = {
        "size": 0,
        "query": {
            "bool": {
                "filter": [
                    {"term": {"event_type": "click"}},
                    {"range": {"timestamp": {"gte": gte}}}
                ]
            }
        },
        "aggs": {
            "top_clicked": {"terms": {"field": "doc_id", "size": size}}
        }
    }

    res = es.search(index=ANALYTICS_INDEX, body=body)
    buckets = res.get("aggregations", {}).get("top_clicked", {}).get("buckets", [])
    return {"range_days": days, "top": [{"doc_id": b.get("key"), "clicks": b.get("doc_count")} for b in buckets]}

