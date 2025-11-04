import asyncio
import time
import random
from typing import Any, Dict, List, Optional

import aiohttp


DEFAULT_TIMEOUT_SECONDS = 10
DEFAULT_RETRIES = 2
DEFAULT_BACKOFF_BASE = 0.4
DEFAULT_PREVIEW_BYTES = 2048


def _is_textual(content_type: Optional[str]) -> bool:
    if not content_type:
        return False
    ct = content_type.lower()
    return (
        "text/" in ct
        or "json" in ct
        or "xml" in ct
        or "javascript" in ct
        or "+json" in ct
        or "+xml" in ct
    )


async def fetch_url(
    session: aiohttp.ClientSession,
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    retries: int = DEFAULT_RETRIES,
    backoff_base: float = DEFAULT_BACKOFF_BASE,
    preview_bytes: int = DEFAULT_PREVIEW_BYTES,
    semaphore: Optional[asyncio.Semaphore] = None,
) -> Dict[str, Any]:
    """
    Fetch a single URL using aiohttp with retries, timeout, and optional concurrency control.

    Returns a structured dict containing metadata and a small body preview for text content.
    """
    attempt = 0
    last_error: Optional[str] = None

    # Compose timeout once to avoid recreating per attempt
    client_timeout = aiohttp.ClientTimeout(total=timeout)

    while attempt <= retries:
        attempt += 1
        started = time.perf_counter()
        try:
            if semaphore is not None:
                async with semaphore:
                    async with session.get(url, timeout=client_timeout) as resp:
                        elapsed_ms = (time.perf_counter() - started) * 1000.0
                        content_type = resp.headers.get("Content-Type")
                        status = resp.status
                        ok = 200 <= status < 400

                        # Read a small preview to avoid loading entire bodies
                        chunk = await resp.content.read(preview_bytes)
                        preview: Optional[str] = None

                        if _is_textual(content_type):
                            try:
                                preview = chunk.decode("utf-8", errors="replace")
                            except Exception:
                                preview = None

                        return {
                            "url": url,
                            "ok": ok,
                            "status": status,
                            "elapsed_ms": round(elapsed_ms, 2),
                            "content_type": content_type,
                            "body_preview": preview,
                            "bytes_previewed": len(chunk),
                            "error": None,
                            "attempts": attempt,
                        }
            else:
                async with session.get(url, timeout=client_timeout) as resp:
                    elapsed_ms = (time.perf_counter() - started) * 1000.0
                    content_type = resp.headers.get("Content-Type")
                    status = resp.status
                    ok = 200 <= status < 400

                    chunk = await resp.content.read(preview_bytes)
                    preview: Optional[str] = None
                    if _is_textual(content_type):
                        try:
                            preview = chunk.decode("utf-8", errors="replace")
                        except Exception:
                            preview = None

                    return {
                        "url": url,
                        "ok": ok,
                        "status": status,
                        "elapsed_ms": round(elapsed_ms, 2),
                        "content_type": content_type,
                        "body_preview": preview,
                        "bytes_previewed": len(chunk),
                        "error": None,
                        "attempts": attempt,
                    }
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            last_error = f"{type(e).__name__}: {e}"
            if attempt <= retries:
                # Exponential backoff with jitter
                delay = (backoff_base * (2 ** (attempt - 1))) * (0.5 + random.random())
                await asyncio.sleep(delay)
            else:
                elapsed_ms = (time.perf_counter() - started) * 1000.0
                return {
                    "url": url,
                    "ok": False,
                    "status": None,
                    "elapsed_ms": round(elapsed_ms, 2),
                    "content_type": None,
                    "body_preview": None,
                    "bytes_previewed": 0,
                    "error": last_error,
                    "attempts": attempt,
                }
        except Exception as e:
            # Non-retryable unexpected error surfaced immediately
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            return {
                "url": url,
                "ok": False,
                "status": None,
                "elapsed_ms": round(elapsed_ms, 2),
                "content_type": None,
                "body_preview": None,
                "bytes_previewed": 0,
                "error": f"UnexpectedError: {type(e).__name__}: {e}",
                "attempts": attempt,
            }

    # Should not reach here
    return {
        "url": url,
        "ok": False,
        "status": None,
        "elapsed_ms": None,
        "content_type": None,
        "body_preview": None,
        "bytes_previewed": 0,
        "error": last_error or "Unknown error",
        "attempts": attempt,
    }


async def fetch_all_with_session(
    session: aiohttp.ClientSession,
    urls: List[str],
    *,
    concurrency: int = 10,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    retries: int = DEFAULT_RETRIES,
    backoff_base: float = DEFAULT_BACKOFF_BASE,
    preview_bytes: int = DEFAULT_PREVIEW_BYTES,
) -> List[Dict[str, Any]]:
    """Fetch multiple URLs concurrently using a provided session."""
    semaphore = asyncio.Semaphore(concurrency) if concurrency and concurrency > 0 else None

    tasks = [
        asyncio.create_task(
            fetch_url(
                session,
                url,
                timeout=timeout,
                retries=retries,
                backoff_base=backoff_base,
                preview_bytes=preview_bytes,
                semaphore=semaphore,
            )
        )
        for url in urls
    ]

    results = await asyncio.gather(*tasks, return_exceptions=False)
    return results


async def fetch_all(
    urls: List[str],
    *,
    concurrency: int = 10,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    retries: int = DEFAULT_RETRIES,
    backoff_base: float = DEFAULT_BACKOFF_BASE,
    preview_bytes: int = DEFAULT_PREVIEW_BYTES,
    user_agent: str = "async-io-concurrent-fetcher/1.0",
) -> List[Dict[str, Any]]:
    """Convenience wrapper that manages its own ClientSession lifecycle."""
    connector = aiohttp.TCPConnector(limit=0)  # let semaphore enforce concurrency
    headers = {"User-Agent": user_agent}
    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        return await fetch_all_with_session(
            session,
            urls,
            concurrency=concurrency,
            timeout=timeout,
            retries=retries,
            backoff_base=backoff_base,
            preview_bytes=preview_bytes,
        )

