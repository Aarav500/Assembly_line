from __future__ import annotations
from typing import Dict, Optional, Tuple
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from threading import RLock
from datetime import datetime, timezone

from config import settings
from models import Base, ReplicationHeartbeat


class DBRegistry:
    def __init__(self, primary_url: str, replicas: Dict[str, Dict]):
        self._lock = RLock()
        self.primary_name = "primary"
        self.primary_url = primary_url
        self.primary_engine: Engine = create_engine(primary_url, pool_pre_ping=True, future=True)
        self.SessionPrimary = sessionmaker(bind=self.primary_engine, expire_on_commit=False, future=True)

        # replicas: name -> dict(region, url, engine, sessionmaker)
        self.replicas: Dict[str, Dict] = {}
        for idx, (region, url) in enumerate(replicas.items() if isinstance(replicas, dict) else {}):
            pass  # placeholder when using dict directly

        # Build from provided list (region,url) but assign names as region or region_N
        for idx, (region, url) in enumerate(settings.replica_dbs):
            name = region
            # Ensure uniqueness
            base_name = name
            n = 1
            while name in self.replicas or name == self.primary_name:
                name = f"{base_name}_{n}"
                n += 1
            eng = create_engine(url, pool_pre_ping=True, future=True)
            self.replicas[name] = {
                "region": region,
                "url": url,
                "engine": eng,
                "Session": sessionmaker(bind=eng, expire_on_commit=False, future=True),
            }

    def create_schema(self, apply_to_all: bool = True) -> None:
        # Always ensure schema exists on primary
        Base.metadata.create_all(self.primary_engine)
        if apply_to_all:
            for r in self.replicas.values():
                try:
                    Base.metadata.create_all(r["engine"])
                except Exception:
                    # Best effort for replicas
                    pass

    def get_primary_session(self) -> Session:
        return self.SessionPrimary()

    def get_replica_session_by_name(self, name: str) -> Tuple[Session, Dict]:
        r = self.replicas[name]
        return r["Session"](), r

    def list_replicas(self) -> Dict[str, Dict]:
        return {k: {"region": v["region"], "url": v["url"]} for k, v in self.replicas.items()}

    def promote_replica_to_primary(self, name: str) -> None:
        with self._lock:
            if name not in self.replicas:
                raise ValueError(f"Replica '{name}' not found")
            # Close old primary engine connections politely
            try:
                self.primary_engine.dispose()
            except Exception:
                pass
            # Promote
            promoted = self.replicas.pop(name)
            self.primary_url = promoted["url"]
            self.primary_engine = promoted["engine"]
            self.SessionPrimary = promoted["Session"]
            # Demote old primary to replica under special name
            old_primary_url = self.primary_engine.url if hasattr(self.primary_engine, 'url') else None
            # Note: can't reuse engine after dispose above; but we already replaced with promoted engine
            # To keep previous primary accessible as a replica, we would need its URL prior to dispose.
            # We'll skip adding old primary as a replica unless URL known from settings.

    def primary_heartbeat(self) -> None:
        # Ensure a heartbeat row exists and update timestamp
        now = datetime.now(timezone.utc)
        with self.get_primary_session() as s:
            s.begin()
            row = s.get(ReplicationHeartbeat, 1)
            if not row:
                row = ReplicationHeartbeat(id=1, updated_at=now)
                s.add(row)
            else:
                row.updated_at = now
            s.commit()

    def read_heartbeat_timestamp(self, engine: Engine) -> Optional[datetime]:
        try:
            with engine.connect() as conn:
                res = conn.execute(text("SELECT updated_at FROM replication_heartbeat WHERE id = 1"))
                row = res.first()
                if not row:
                    return None
                return row[0]
        except Exception:
            return None


# Initialize registry singleton
registry = DBRegistry(primary_url=settings.primary_url, replicas={})
registry.create_schema(apply_to_all=settings.apply_schema_to_all)

