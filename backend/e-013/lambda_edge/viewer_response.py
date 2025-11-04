# Lambda@Edge Viewer-Response function to enrich caching and timing headers

def handler(event, context):
    record = event.get("Records", [{}])[0]
    resp = record.get("cf", {}).get("response", {})
    headers = resp.get("headers", {})

    # Strengthen caching if origin was permissive
    cache_control = None
    if "cache-control" in headers:
        cache_control = headers["cache-control"][0]["value"]
    if not cache_control or "no-store" in cache_control:
        headers["cache-control"] = [{
            "key": "Cache-Control",
            "value": "public, max-age=30, s-maxage=300, stale-while-revalidate=30, stale-if-error=86400",
        }]

    # Add Timing-Allow-Origin and Server-Timing hint (approx; no duration available here)
    headers.setdefault("timing-allow-origin", []).append({"key": "Timing-Allow-Origin", "value": "*"})
    headers.setdefault("server-timing", []).append({"key": "Server-Timing", "value": "edge;desc=viewer-response"})

    # Security headers (idempotent)
    headers.setdefault("x-content-type-options", []).append({"key": "X-Content-Type-Options", "value": "nosniff"})
    headers.setdefault("referrer-policy", []).append({"key": "Referrer-Policy", "value": "same-origin"})

    resp["headers"] = headers
    return resp

