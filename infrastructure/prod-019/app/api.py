from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Any, Optional, List

from .repository import (
    init_db,
    create_local_change_upsert,
    create_local_change_delete,
    ingest_remote_change,
    get_item,
    list_changes,
)
from .config import config

app = FastAPI(title="Multi-Region Eventually Consistent KV")


class WriteRequest(BaseModel):
    key: str
    value: Any


class Change(BaseModel):
    change_id: str
    key: str
    value: Optional[Any] = None
    hlc_ts: str
    updated_by: str
    origin: str
    op: str


class ChangesResponse(BaseModel):
    region: str
    last_seq: int
    changes: List[Change]


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok", "region": config.REGION_ID}


@app.get("/region")
def region():
    return {"region": config.REGION_ID, "node": config.NODE_ID}


@app.post("/write")
def write(req: WriteRequest):
    ch = create_local_change_upsert(req.key, req.value)
    return {"status": "ok", "hlc_ts": ch["hlc_ts"], "change_id": ch["change_id"], "region": config.REGION_ID}


@app.delete("/key/{key}")
def delete_key(key: str):
    ch = create_local_change_delete(key)
    return {"status": "ok", "hlc_ts": ch["hlc_ts"], "change_id": ch["change_id"], "region": config.REGION_ID}


@app.get("/get")
def read(key: str = Query(...)):
    item = get_item(key)
    if not item or item.get("deleted"):
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "key": item["key"],
        "value": item["value"],
        "hlc_ts": item["hlc_ts"],
        "updated_by": item["updated_by"],
        "updated_at": item["updated_at"].isoformat() if item.get("updated_at") else None,
    }


@app.get("/changes", response_model=ChangesResponse)
def get_changes(since_seq: int = 0, limit: int = 500, all: bool = False):
    data = list_changes(since_seq=since_seq, limit=limit, origin_only=(not all))
    return {
        "region": config.REGION_ID,
        "last_seq": data["last_seq"],
        "changes": data["changes"],
    }


@app.post("/ingest")
def ingest(changes: List[Change]):
    applied = 0
    for ch in changes:
        if ingest_remote_change(ch.dict()):
            applied += 1
    return {"status": "ok", "applied": applied}

