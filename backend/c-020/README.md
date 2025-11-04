# Caching & CDN Integration Demo

Minimal Flask application demonstrating Redis caching, Varnish-compatible headers, and Cloud CDN integration.

## Features

- Redis caching with decorators
- CDN-friendly cache headers (Cache-Control, Vary)
- Varnish-compatible configuration
- Multiple cache strategies (short/long TTL)
- Cache invalidation endpoint

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
python app.py
```

## Test

```bash
pytest tests/
```

## Endpoints

- `GET /` - Index with cache headers
- `GET /api/data` - Cached data (5 min Redis, 10 min CDN)
- `GET /api/user/<id>` - Cached user data (10 min Redis, 20 min CDN)
- `POST /api/cache/clear` - Clear Redis cache
- `GET /health` - Health check (no cache)
- `GET /api/static-content` - Long-term cached content (1 day browser, 7 days CDN)

## Notes

- Redis is optional; app works without it
- Cache headers are CDN/Varnish compatible
- Use s-maxage for CDN/proxy caching
- Use max-age for browser caching
