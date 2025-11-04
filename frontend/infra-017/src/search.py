from typing import Any, Dict, List, Optional, Tuple
from elasticsearch import Elasticsearch

DEFAULT_FACET_SIZE = 10


def _build_query(q: Optional[str], filters: Dict[str, Any]) -> Dict[str, Any]:
    must: List[Dict[str, Any]] = []
    should: List[Dict[str, Any]] = []
    filter_clauses: List[Dict[str, Any]] = []

    if q:
        must.append({
            "multi_match": {
                "query": q,
                "type": "best_fields",
                "fields": [
                    "title^3",
                    "title.autocomplete^2",
                    "description"
                ],
                "operator": "and",
                "fuzziness": "AUTO"
            }
        })
        should.extend([
            {"match_phrase": {"title": {"query": q, "boost": 3}}},
            {"match_phrase": {"description": {"query": q, "boost": 1}}}
        ])

    if filters.get("category"):
        filter_clauses.append({"terms": {"category": filters["category"]}})
    if filters.get("brand"):
        filter_clauses.append({"terms": {"brand": filters["brand"]}})
    if filters.get("tags"):
        filter_clauses.append({"terms": {"tags": filters["tags"]}})
    price_min = filters.get("price_min")
    price_max = filters.get("price_max")
    if price_min is not None or price_max is not None:
        rng: Dict[str, Any] = {}
        if price_min is not None:
            rng["gte"] = price_min
        if price_max is not None:
            rng["lte"] = price_max
        filter_clauses.append({"range": {"price": rng}})

    bool_query: Dict[str, Any] = {"bool": {}}
    if must:
        bool_query["bool"]["must"] = must
    if should:
        bool_query["bool"]["should"] = should
        bool_query["bool"]["minimum_should_match"] = 0 if must else 1
    if filter_clauses:
        bool_query["bool"]["filter"] = filter_clauses

    return bool_query


def _build_aggs() -> Dict[str, Any]:
    return {
        "by_category": {"terms": {"field": "category", "size": DEFAULT_FACET_SIZE}},
        "by_brand": {"terms": {"field": "brand", "size": DEFAULT_FACET_SIZE}},
        "by_tags": {"terms": {"field": "tags", "size": DEFAULT_FACET_SIZE}},
        "price_stats": {"stats": {"field": "price"}}
    }


def _parse_aggs(aggs: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    facets = {
        "category": [{"key": b["key"], "count": b["doc_count"]} for b in aggs.get("by_category", {}).get("buckets", [])],
        "brand": [{"key": b["key"], "count": b["doc_count"]} for b in aggs.get("by_brand", {}).get("buckets", [])],
        "tags": [{"key": b["key"], "count": b["doc_count"]} for b in aggs.get("by_tags", {}).get("buckets", [])],
    }
    stats_src = aggs.get("price_stats", {})
    stats = {
        "price": {
            "min": stats_src.get("min"),
            "max": stats_src.get("max"),
            "avg": stats_src.get("avg"),
            "sum": stats_src.get("sum"),
            "count": stats_src.get("count"),
        }
    }
    return facets, stats


def search(
    es: Elasticsearch,
    index: str,
    q: Optional[str],
    filters: Dict[str, Any],
    page: int = 1,
    size: int = 10,
    sort: Optional[str] = None,
    fields: Optional[List[str]] = None
) -> Dict[str, Any]:
    from_ = max(0, (page - 1) * size)
    body: Dict[str, Any] = {
        "track_total_hits": True,
        "query": _build_query(q, filters),
        "aggs": _build_aggs(),
        "from": from_,
        "size": size,
        "highlight": {
            "pre_tags": ["<em>"],
            "post_tags": ["</em>"],
            "fields": {"title": {}, "description": {}}
        }
    }

    if sort == "price_asc":
        body["sort"] = [{"price": {"order": "asc"}}]
    elif sort == "price_desc":
        body["sort"] = [{"price": {"order": "desc"}}]
    elif sort == "newest":
        body["sort"] = [{"created_at": {"order": "desc"}}]
    else:
        body["sort"] = ["_score"]

    if fields:
        body["_source"] = fields

    resp = es.search(index=index, **body)

    hits = []
    for h in resp["hits"]["hits"]:
        src = h.get("_source", {})
        if "highlight" in h:
            src["_highlight"] = h["highlight"]
        src["_id"] = h.get("_id")
        src["_score"] = h.get("_score")
        hits.append(src)

    facets, stats = _parse_aggs(resp.get("aggregations", {}))

    return {
        "total": (resp.get("hits", {}).get("total", {}) or {}).get("value", 0),
        "took": resp.get("took", 0),
        "page": page,
        "size": size,
        "hits": hits,
        "facets": facets,
        "stats": stats
    }


def autocomplete(es: Elasticsearch, index: str, prefix: str, size: int = 8) -> Dict[str, Any]:
    body = {
        "size": 0,
        "suggest": {
            "title_suggest": {
                "prefix": prefix,
                "completion": {
                    "field": "title_suggest",
                    "size": size,
                    "skip_duplicates": True
                }
            }
        }
    }

    sresp = es.search(index=index, **body)

    suggestions: List[str] = []
    try:
        opts = sresp["suggest"]["title_suggest"][0]["options"]
        suggestions = [o["text"] for o in opts]
    except Exception:
        suggestions = []

    # Also fetch some top documents using edge-ngram field for search-as-you-type
    dresp = es.search(index=index, **{
        "size": size,
        "query": {
            "multi_match": {
                "query": prefix,
                "type": "bool_prefix",
                "fields": ["title.autocomplete^2", "title", "description"]
            }
        },
        "_source": ["title", "brand", "category", "price", "tags"]
    })

    hits = []
    for h in dresp["hits"]["hits"]:
        src = h.get("_source", {})
        src["_id"] = h.get("_id")
        src["_score"] = h.get("_score")
        hits.append(src)

    return {"suggestions": suggestions, "took": sresp.get("took", 0), "hits": hits}

