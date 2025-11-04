import asyncio
import uvicorn

from app.api import app
from app.sync import sync_loop
from app.config import config
from app.db import init_pool


if __name__ == "__main__":
    init_pool()

    loop = asyncio.get_event_loop()

    # Start background sync task if peers configured
    if config.PEERS:
        loop.create_task(sync_loop())

    uvicorn.run(app, host="0.0.0.0", port=config.PORT)

