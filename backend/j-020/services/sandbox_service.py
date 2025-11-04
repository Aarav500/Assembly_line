import os
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session, sessionmaker

from models import Sandbox
from providers import get_provider


class SandboxService:
    def __init__(self, session_factory: sessionmaker, provider_name: str, data_dir: str, templates_dir: str, default_ttl_minutes: int = 60):
        self.session_factory = session_factory
        self.provider_name = provider_name
        self.provider = get_provider(provider_name, data_dir=data_dir, templates_dir=templates_dir)
        self.data_dir = data_dir
        self.templates_dir = templates_dir
        self.default_ttl_minutes = int(default_ttl_minutes or 60)

    def _new_session(self) -> Session:
        return self.session_factory()

    def serialize_sandbox(self, sb: Sandbox) -> Dict[str, Any]:
        data = {
            "id": sb.id,
            "name": sb.name,
            "template": sb.template,
            "status": sb.status,
            "created_at": sb.created_at.isoformat() + "Z",
            "updated_at": sb.updated_at.isoformat() + "Z",
            "expires_at": sb.expires_at.isoformat() + "Z" if sb.expires_at else None,
            "provider": sb.provider,
            "provider_data": sb.provider_data or {},
            "last_error": sb.last_error,
        }
        return data

    def list_sandboxes(self, session: Session) -> List[Sandbox]:
        return session.query(Sandbox).order_by(Sandbox.created_at.desc()).all()

    def get_sandbox(self, session: Session, sandbox_id: str) -> Optional[Sandbox]:
        return session.get(Sandbox, sandbox_id)

    def create_sandbox(self, name: Optional[str], template: str, ttl_minutes: Optional[int], env: Dict[str, str]) -> Sandbox:
        session = self._new_session()
        try:
            sandbox_id = str(uuid.uuid4())
            sb = Sandbox(
                id=sandbox_id,
                name=name,
                template=template,
                status="provisioning",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(minutes=(ttl_minutes or self.default_ttl_minutes)),
                provider=self.provider_name,
                provider_data=None,
            )
            session.add(sb)
            session.commit()

            # call provider
            pdata = self.provider.provision(sandbox_id=sandbox_id, template=template, env=env or {})
            sb.provider_data = pdata
            sb.status = "running"
            sb.touch()
            session.commit()
            return sb
        except Exception as e:
            # update error
            sb = session.get(Sandbox, sandbox_id) if 'sandbox_id' in locals() else None
            if sb:
                sb.status = "error"
                sb.last_error = str(e)
                sb.touch()
                session.commit()
            raise
        finally:
            session.close()

    def teardown_sandbox(self, sandbox_id: str, reason: str = "user") -> Optional[Sandbox]:
        session = self._new_session()
        try:
            sb = session.get(Sandbox, sandbox_id)
            if not sb:
                return None
            # call provider teardown
            try:
                self.provider.teardown(sandbox_id, sb.provider_data or {})
            except Exception:
                # swallow teardown errors but proceed to mark terminated
                pass
            sb.status = "expired" if reason == "expired" else "terminated"
            sb.touch()
            session.commit()
            return sb
        finally:
            session.close()

    def extend_sandbox(self, sb: Sandbox, ttl_minutes: int) -> datetime:
        session = self._new_session()
        try:
            sb = session.get(Sandbox, sb.id)
            if not sb:
                raise ValueError("Sandbox not found")
            base = sb.expires_at if sb.expires_at and sb.expires_at > datetime.utcnow() else datetime.utcnow()
            sb.expires_at = base + timedelta(minutes=ttl_minutes)
            sb.touch()
            session.commit()
            return sb.expires_at
        finally:
            session.close()

    def refresh_status(self, sb: Sandbox) -> Dict[str, Any]:
        session = self._new_session()
        try:
            sb = session.get(Sandbox, sb.id)
            st = self.provider.status(sb.id, sb.provider_data or {})
            # optionally map provider state to sb.status
            mapped = st.get("state")
            if mapped in ("running", "stopped"):
                sb.status = mapped
            sb.provider_data = {**(sb.provider_data or {}), **{"ports": st.get("ports", [])}}
            sb.touch()
            session.commit()
            return st
        finally:
            session.close()

    def stop_sandbox(self, sandbox_id: str) -> Optional[Sandbox]:
        session = self._new_session()
        try:
            sb = session.get(Sandbox, sandbox_id)
            if not sb:
                return None
            self.provider.stop(sandbox_id, sb.provider_data or {})
            sb.status = "stopped"
            sb.touch()
            session.commit()
            return sb
        finally:
            session.close()

    def start_sandbox(self, sandbox_id: str) -> Optional[Sandbox]:
        session = self._new_session()
        try:
            sb = session.get(Sandbox, sandbox_id)
            if not sb:
                return None
            self.provider.start(sandbox_id, sb.provider_data or {})
            sb.status = "running"
            sb.touch()
            session.commit()
            return sb
        finally:
            session.close()

    def reap_expired(self) -> int:
        session = self._new_session()
        try:
            now = datetime.utcnow()
            q = session.query(Sandbox).filter(Sandbox.expires_at != None, Sandbox.expires_at < now, Sandbox.status.in_(["running", "provisioning", "stopped"]))
            to_reap = q.all()
            count = 0
            for sb in to_reap:
                try:
                    self.provider.teardown(sb.id, sb.provider_data or {})
                except Exception:
                    pass
                sb.status = "expired"
                sb.touch()
                count += 1
            session.commit()
            return count
        finally:
            session.close()

