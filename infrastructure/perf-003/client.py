import argparse
import asyncio
import json
from typing import List

import aiohttp

from fetcher import fetch_all


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Concurrent async fetcher demo")
    p.add_argument("urls", nargs="*", help="URLs to fetch concurrently")
    p.add_argument("--concurrency", "-c", type=int, default=10, help="Max concurrent requests")
    p.add_argument("--timeout", "-t", type=float, default=10.0, help="Request timeout (seconds)")
    p.add_argument("--retries", "-r", type=int, default=2, help="Number of retries on failure")
    p.add_argument("--preview-bytes", type=int, default=2048, help="Max bytes to preview from each response")
    p.add_argument(
        "--server",
        help="Optional server endpoint to POST /fetch (e.g., http://localhost:8080)",
        default=None,
    )
    return p.parse_args()


async def run_direct(urls: List[str], concurrency: int, timeout: float, retries: int, preview_bytes: int) -> None:
    results = await fetch_all(
        urls,
        concurrency=concurrency,
        timeout=timeout,
        retries=retries,
        preview_bytes=preview_bytes,
    )
    summary = {
        "count": len(results),
        "ok_count": sum(1 for r in results if r.get("ok")),
        "results": results,
    }
    print(json.dumps(summary, indent=2))


async def run_via_server(server: str, urls: List[str], concurrency: int, timeout: float, retries: int, preview_bytes: int) -> None:
    payload = {
        "urls": urls,
        "concurrency": concurrency,
        "timeout": timeout,
        "retries": retries,
        "preview_bytes": preview_bytes,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{server.rstrip('/')}/fetch", json=payload) as resp:
            text = await resp.text()
            print(text)


def main() -> None:
    args = parse_args()

    if not args.urls:
        # Default demo targets if none provided
        args.urls = [
            "https://httpbin.org/get",
            "https://httpbin.org/delay/1",
            "https://httpbin.org/status/200",
            "https://httpbin.org/status/404",
            "https://example.com",
        ]

    if args.server:
        asyncio.run(run_via_server(args.server, args.urls, args.concurrency, args.timeout, args.retries, args.preview_bytes))
    else:
        asyncio.run(run_direct(args.urls, args.concurrency, args.timeout, args.retries, args.preview_bytes))


if __name__ == "__main__":
    main()

