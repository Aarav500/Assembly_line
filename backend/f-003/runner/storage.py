from __future__ import annotations
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Float, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, scoped_session

Base = declarative_base()


class FlowRunORM(Base):
    __tablename__ = 'flow_runs'
    id = Column(Integer, primary_key=True)
    flow_id = Column(String, index=True, nullable=False)
    flow_name = Column(String, nullable=False)
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=False)
    duration_ms = Column(Float, nullable=False)
    success = Column(Boolean, nullable=False)
    error_summary = Column(Text, nullable=True)
    details_json = Column(Text, nullable=True)
    steps = relationship("StepRunORM", back_populates="flow_run", cascade="all, delete-orphan")


class StepRunORM(Base):
    __tablename__ = 'step_runs'
    id = Column(Integer, primary_key=True)
    flow_run_id = Column(Integer, ForeignKey('flow_runs.id'), index=True)
    step_name = Column(String, nullable=False)
    method = Column(String, nullable=False)
    url = Column(Text, nullable=False)
    status_code = Column(Integer, nullable=True)
    success = Column(Boolean, nullable=False)
    response_ms = Column(Float, nullable=False)
    error = Column(Text, nullable=True)
    response_excerpt = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    flow_run = relationship("FlowRunORM", back_populates="steps")


class AlertEventORM(Base):
    __tablename__ = 'alerts'
    id = Column(Integer, primary_key=True)
    flow_id = Column(String, index=True, nullable=False)
    flow_name = Column(String, nullable=False)
    event_type = Column(String, nullable=False)  # failure or recovery
    severity = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    sent_channels = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class FlowStateORM(Base):
    __tablename__ = 'flow_state'
    id = Column(Integer, primary_key=True)
    flow_id = Column(String, unique=True, nullable=False)
    last_status = Column(String, nullable=False, default='unknown')
    consecutive_failures = Column(Integer, nullable=False, default=0)
    last_alerted_at = Column(DateTime, nullable=True)


class Storage:
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url, pool_pre_ping=True, future=True)
        self.SessionLocal = scoped_session(sessionmaker(bind=self.engine, autocommit=False, autoflush=False))

    def init_db(self):
        Base.metadata.create_all(self.engine)

    def create_flow_run(self, flow_id: str, flow_name: str, started_at: float, finished_at: float, duration_ms: float, success: bool, error_summary: Optional[str], details: Dict[str, Any]) -> Dict[str, Any]:
        db = self.SessionLocal()
        try:
            orm = FlowRunORM(
                flow_id=flow_id,
                flow_name=flow_name,
                started_at=datetime.utcfromtimestamp(started_at),
                finished_at=datetime.utcfromtimestamp(finished_at),
                duration_ms=duration_ms,
                success=success,
                error_summary=error_summary,
                details_json=json.dumps(details, ensure_ascii=False)
            )
            db.add(orm)
            db.commit()
            db.refresh(orm)
            return self._flow_run_to_dict(orm)
        finally:
            db.close()

    def create_step_run(self, flow_run_id: int, step_name: str, method: str, url: str, status_code: Optional[int], success: bool, response_ms: float, error: Optional[str], response_excerpt: Optional[str]):
        db = self.SessionLocal()
        try:
            orm = StepRunORM(
                flow_run_id=flow_run_id,
                step_name=step_name,
                method=method,
                url=url,
                status_code=status_code,
                success=success,
                response_ms=response_ms,
                error=error,
                response_excerpt=response_excerpt,
            )
            db.add(orm)
            db.commit()
        finally:
            db.close()

    def get_flow_runs(self, flow_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        db = self.SessionLocal()
        try:
            q = db.query(FlowRunORM)
            if flow_id:
                q = q.filter(FlowRunORM.flow_id == flow_id)
            q = q.order_by(FlowRunORM.id.desc()).limit(limit)
            return [self._flow_run_to_dict(x) for x in q.all()]
        finally:
            db.close()

    def get_flow_run(self, run_id: int) -> Optional[Dict[str, Any]]:
        db = self.SessionLocal()
        try:
            orm = db.query(FlowRunORM).filter(FlowRunORM.id == run_id).one_or_none()
            if not orm:
                return None
            return self._flow_run_to_dict(orm)
        finally:
            db.close()

    def get_step_runs(self, run_id: int) -> List[Dict[str, Any]]:
        db = self.SessionLocal()
        try:
            steps = db.query(StepRunORM).filter(StepRunORM.flow_run_id == run_id).order_by(StepRunORM.id.asc()).all()
            out = []
            for s in steps:
                out.append({
                    "id": s.id,
                    "step_name": s.step_name,
                    "method": s.method,
                    "url": s.url,
                    "status_code": s.status_code,
                    "success": s.success,
                    "response_ms": round(s.response_ms, 2),
                    "error": s.error,
                    "response_excerpt": s.response_excerpt,
                    "created_at": s.created_at.isoformat() + "Z",
                })
            return out
        finally:
            db.close()

    def _flow_run_to_dict(self, orm: FlowRunORM) -> Dict[str, Any]:
        details = None
        try:
            details = json.loads(orm.details_json) if orm.details_json else None
        except Exception:
            details = None
        return {
            "id": orm.id,
            "flow_id": orm.flow_id,
            "flow_name": orm.flow_name,
            "started_at": orm.started_at.isoformat() + "Z",
            "finished_at": orm.finished_at.isoformat() + "Z",
            "duration_ms": round(orm.duration_ms, 2),
            "success": orm.success,
            "error_summary": orm.error_summary,
            "details": details,
        }

    def get_or_create_flow_state(self, flow_id: str) -> FlowStateORM:
        db = self.SessionLocal()
        try:
            st = db.query(FlowStateORM).filter(FlowStateORM.flow_id == flow_id).one_or_none()
            if not st:
                st = FlowStateORM(flow_id=flow_id, last_status='unknown', consecutive_failures=0, last_alerted_at=None)
                db.add(st)
                db.commit()
                db.refresh(st)
            return st
        finally:
            db.close()

    def update_flow_state(self, flow_id: str, last_status: str, consecutive_failures: int, last_alerted_at: Optional[datetime]):
        db = self.SessionLocal()
        try:
            st = db.query(FlowStateORM).filter(FlowStateORM.flow_id == flow_id).one_or_none()
            if not st:
                st = FlowStateORM(flow_id=flow_id)
            st.last_status = last_status
            st.consecutive_failures = consecutive_failures
            st.last_alerted_at = last_alerted_at
            db.merge(st)
            db.commit()
        finally:
            db.close()

    def create_alert_event(self, flow_id: str, flow_name: str, event_type: str, severity: str, message: str, sent_channels: List[str]):
        db = self.SessionLocal()
        try:
            orm = AlertEventORM(
                flow_id=flow_id,
                flow_name=flow_name,
                event_type=event_type,
                severity=severity,
                message=message,
                sent_channels=json.dumps(sent_channels)
            )
            db.add(orm)
            db.commit()
        finally:
            db.close()

    def get_alerts(self, flow_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        db = self.SessionLocal()
        try:
            q = db.query(AlertEventORM)
            if flow_id:
                q = q.filter(AlertEventORM.flow_id == flow_id)
            q = q.order_by(AlertEventORM.id.desc()).limit(limit)
            out = []
            for a in q.all():
                try:
                    channels = json.loads(a.sent_channels) if a.sent_channels else []
                except Exception:
                    channels = []
                out.append({
                    "id": a.id,
                    "flow_id": a.flow_id,
                    "flow_name": a.flow_name,
                    "event_type": a.event_type,
                    "severity": a.severity,
                    "message": a.message,
                    "sent_channels": channels,
                    "created_at": a.created_at.isoformat() + "Z",
                })
            return out
        finally:
            db.close()

