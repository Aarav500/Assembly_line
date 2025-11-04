import asyncio
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app

from .config import load_config
from .prom_client import PrometheusClient
from .scheduler import Scheduler, AppState


cfg = load_config()
app = FastAPI(title="Cost Tracking and Resource Optimization", version="1.0.0")
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

state = AppState()
prom = PrometheusClient(cfg.prometheus.url, verify=cfg.prometheus.verify_tls, timeout_seconds=cfg.prometheus.timeout_seconds)
scheduler = Scheduler(cfg, prom, state)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(scheduler.run())


@app.on_event("shutdown")
async def shutdown_event():
    await prom.close()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/recommendations")
async def get_recommendations():
    return JSONResponse(content=state.last_recommendations or {"status": "pending"})

