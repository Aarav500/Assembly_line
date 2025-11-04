import asyncio
import httpx
from typing import List

from .config import config
from .repository import ensure_peer_state, get_peer_last_seq, update_peer_last_seq, ingest_remote_change


async def sync_with_peer(client: httpx.AsyncClient, peer_url: str):
    ensure_peer_state(peer_url)
    last_seq = get_peer_last_seq(peer_url)
    params = {"since_seq": last_seq, "limit": config.CHANGE_BATCH_SIZE}
    try:
        r = await client.get(f"{peer_url}/changes", params=params, timeout=30.0)
        r.raise_for_status()
        payload = r.json()
        changes: List[dict] = payload.get("changes", [])
        max_seq = payload.get("last_seq", last_seq)
        applied_any = False
        for ch in changes:
            if ingest_remote_change(ch):
                applied_any = True
        # update last_seq to max_seq regardless of applied_any to avoid stalling
        update_peer_last_seq(peer_url, max_seq)
        return {"peer": peer_url, "received": len(changes), "applied_any": applied_any}
    except Exception as e:
        return {"peer": peer_url, "error": str(e)}


async def sync_loop():
    if not config.PEERS:
        return
    async with httpx.AsyncClient() as client:
        while True:
            tasks = [sync_with_peer(client, p) for p in config.PEERS]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            # Optionally log results here
            await asyncio.sleep(config.SYNC_INTERVAL_SECONDS)

