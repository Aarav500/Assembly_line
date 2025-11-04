import asyncio
import logging
from typing import Any, Dict, List, Optional

from aiohttp import web
import aiohttp

from fetcher import fetch_all_with_session


logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("async-server")


async def create_app() -> web.Application:
    app = web.Application()

    async def on_startup(app: web.Application) -> None:
        # One shared session for connection pooling across requests
        connector = aiohttp.TCPConnector(limit=0)
        headers = {"User-Agent": "async-io-concurrent-server/1.0"}
        app["http_session"] = aiohttp.ClientSession(connector=connector, headers=headers)
        logger.info("ClientSession initialized")

    async def on_cleanup(app: web.Application) -> None:
        session: aiohttp.ClientSession = app["http_session"]
        await session.close()
        logger.info("ClientSession closed")

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    async def health(_: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    async def sleep_handler(request: web.Request) -> web.Response:
        try:
            delay = float(request.query.get("delay", "1"))
        except ValueError:
            delay = 1.0
        await asyncio.sleep(max(delay, 0.0))
        return web.json_response({"slept": delay})

    async def fetch_handler(request: web.Request) -> web.Response:
        # Expected JSON body: {"urls": [...], "concurrency": 10, "timeout": 10, "retries": 2}
        try:
            payload = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON body"}, status=400)

        urls: Optional[List[str]] = payload.get("urls")
        if not isinstance(urls, list) or not all(isinstance(u, str) for u in urls):
            return web.json_response({"error": "Field 'urls' must be a list of strings"}, status=400)

        concurrency = payload.get("concurrency", 10)
        timeout = payload.get("timeout", 10)
        retries = payload.get("retries", 2)
        preview_bytes = payload.get("preview_bytes", 2048)

        # Basic validation
        try:
            concurrency = int(concurrency)
            timeout = float(timeout)
            retries = int(retries)
            preview_bytes = int(preview_bytes)
        except Exception:
            return web.json_response({"error": "Invalid numeric parameter types"}, status=400)

        session: aiohttp.ClientSession = request.app["http_session"]

        results = await fetch_all_with_session(
            session,
            urls,
            concurrency=max(concurrency, 1),
            timeout=max(timeout, 0.1),
            retries=max(retries, 0),
            preview_bytes=max(preview_bytes, 0),
        )

        ok_count = sum(1 for r in results if r.get("ok"))
        return web.json_response({
            "count": len(results),
            "ok_count": ok_count,
            "results": results,
        })

    app.router.add_get("/health", health)
    app.router.add_get("/sleep", sleep_handler)
    app.router.add_post("/fetch", fetch_handler)

    return app


def main() -> None:
    web.run_app(
        create_app(),
        host="0.0.0.0",
        port=8080,
        access_log=None,
    )


if __name__ == "__main__":
    main()

