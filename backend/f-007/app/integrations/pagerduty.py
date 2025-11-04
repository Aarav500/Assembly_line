from datetime import datetime
from typing import Any, Optional
from dateutil import parser
from ..db import SessionLocal
from ..models import ScheduleOverride, User, Schedule
from ..timeutils import parse_dt_to_utc


class PagerDutyWebhook:
    @staticmethod
    def upsert_user_from_email(email: str, name: Optional[str] = None) -> User:
        session = SessionLocal()
        try:
            user = session.query(User).filter(User.email == email).one_or_none()
            if user is None:
                user = User(name=name or email.split("@")[0], email=email)
                session.add(user)
                session.commit()
                session.refresh(user)
            return user
        finally:
            session.close()

    @staticmethod
    def create_override(schedule_id: int, user_id: int, start_iso: str, end_iso: str, reason: str | None = None) -> ScheduleOverride:
        session = SessionLocal()
        try:
            sch = session.get(Schedule, schedule_id)
            if not sch:
                raise ValueError("Schedule not found")
            start_utc = parse_dt_to_utc(start_iso)
            end_utc = parse_dt_to_utc(end_iso)
            ov = ScheduleOverride(schedule_id=schedule_id, user_id=user_id, start_utc=start_utc, end_utc=end_utc, reason=reason)
            session.add(ov)
            session.commit()
            session.refresh(ov)
            return ov
        finally:
            session.close()

    @staticmethod
    def handle_webhook(schedule_id: int, payload: Any) -> dict:
        # This is a simplified handler. Expect payload containing { user: { email, name }, start, end, reason? }
        user_info = (payload or {}).get("user") or {}
        email = user_info.get("email")
        name = user_info.get("name")
        start = payload.get("start")
        end = payload.get("end")
        reason = payload.get("reason", "PagerDuty webhook")

        if not (email and start and end):
            return {"ok": False, "error": "missing user.email/start/end"}

        user = PagerDutyWebhook.upsert_user_from_email(email=email, name=name)
        ov = PagerDutyWebhook.create_override(schedule_id=schedule_id, user_id=user.id, start_iso=start, end_iso=end, reason=reason)
        return {"ok": True, "override": ov.to_dict()}

