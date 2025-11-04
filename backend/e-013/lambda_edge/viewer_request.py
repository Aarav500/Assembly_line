import base64
from urllib.parse import urlencode

# Lambda@Edge Viewer-Request function (Python 3.9+) to optimize for low latency
# - Normalizes query params to improve cache hit ratio
# - Drops cookies for static assets
# - Forces HTTPS
# - Provides synthetic fast path for /edge/ping

def _http_redirect(location: str):
    return {
        "status": "301",
        "statusDescription": "Moved Permanently",
        "headers": {
            "location": [{"key": "Location", "value": location}],
            "cache-control": [{"key": "Cache-Control", "value": "max-age=3600"}],
        },
    }


def handler(event, context):  # noqa: D401
    cf = event.get("Records", [{}])[0].get("cf", {})
    request = cf.get("request", {})
    headers = request.get("headers", {})
    uri = request.get("uri", "/")
    qs = request.get("querystring", "")

    # HTTPS redirect
    proto = headers.get("x-forwarded-proto", [{"value": "http"}])[0]["value"]
    host = headers.get("host", [{"value": ""}])[0]["value"]
    if proto != "https":
        location = f"https://{host}{uri}"
        if qs:
            location += f"?{qs}"
        return _http_redirect(location)

    # Synthetic fast path for health/ping at edge
    if uri.startswith("/edge/ping"):
        body = b"{\"ok\":true}"
        return {
            "status": "200",
            "statusDescription": "OK",
            "headers": {
                "content-type": [{"key": "Content-Type", "value": "application/json"}],
                "cache-control": [{"key": "Cache-Control", "value": "max-age=5, s-maxage=60"}],
            },
            "body": body.decode("utf-8"),
        }

    # Normalize query strings by sorting keys and removing tracking params
    if qs:
        parts = []
        for kv in qs.split("&"):
            if not kv:
                continue
            if kv.startswith("utm_") or kv.startswith("fbclid") or kv.startswith("gclid"):
                continue
            parts.append(kv)
        norm_qs = "&".join(sorted(parts))
        request["querystring"] = norm_qs

    # Strip cookies for static assets to improve caching
    if uri.endswith((".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")):
        if "cookie" in headers:
            headers.pop("cookie", None)
        request["headers"] = headers

    # Geo hint headers pass-through to origin/app
    country = headers.get("cloudfront-viewer-country", [{"value": ""}])[0]["value"]
    if country:
        headers.setdefault("x-geo-country", []).append({"key": "X-Geo-Country", "value": country})

    return request

