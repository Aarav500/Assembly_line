from __future__ import annotations
from datetime import timedelta
from typing import List
from flask import request, jsonify
from flask import Response
from .db import SessionLocal
from .models import User, Schedule, ScheduleParticipant, HandoffHistory, ScheduleOverride
from .timeutils import parse_dt_to_utc, now_utc, current_rotation_index
from .config import Config
from .notifications.slack import SlackNotifier
from .notifications.emailer import EmailNotifier
from .integrations.pagerduty import PagerDutyWebhook


slack_notifier = SlackNotifier(Config.SLACK_BOT_TOKEN, Config.SLACK_DEFAULT_CHANNEL)
email_notifier = EmailNotifier(Config.SMTP_HOST, Config.SMTP_PORT, Config.SMTP_USERNAME, Config.SMTP_PASSWORD, Config.SMTP_FROM_EMAIL, Config.SMTP_USE_TLS)


def register_routes(app):
    @app.post("/api/users")
    def create_user():
        session = SessionLocal()
        try:
            data = request.get_json(force=True)
            name = data.get("name")
            if not name:
                return jsonify({"error": "name is required"}), 400
            user = User(name=name, email=data.get("email"), phone=data.get("phone"), slack_id=data.get("slack_id"))
            session.add(user)
            session.commit()
            session.refresh(user)
            return jsonify(user.to_dict()), 201
        finally:
            session.close()

    @app.get("/api/users")
    def list_users():
        session = SessionLocal()
        try:
            users = session.query(User).order_by(User.id.asc()).all()
            return jsonify([u.to_dict() for u in users])
        finally:
            session.close()

    @app.get("/api/users/<int:user_id>")
    def get_user(user_id: int):
        session = SessionLocal()
        try:
            user = session.get(User, user_id)
            if not user:
                return jsonify({"error": "not found"}), 404
            return jsonify(user.to_dict())
        finally:
            session.close()

    @app.post("/api/schedules")
    def create_schedule():
        session = SessionLocal()
        try:
            data = request.get_json(force=True)
            name = data.get("name")
            timezone = data.get("timezone") or Config.DEFAULT_TIMEZONE
            start_time = data.get("start_time")
            shift_length_minutes = int(data.get("shift_length_minutes") or 720)
            participants: List[int] = data.get("participants") or []  # list of user_ids in order
            notify_slack = bool(data.get("notify_slack", True))
            notify_email = bool(data.get("notify_email", False))
            slack_channel = data.get("slack_channel")

            if not name or not start_time:
                return jsonify({"error": "name and start_time are required"}), 400

            start_utc = parse_dt_to_utc(start_time, tz_hint=timezone)
            sch = Schedule(
                name=name,
                timezone=timezone,
                start_time_utc=start_utc,
                shift_length_minutes=shift_length_minutes,
                notify_slack=notify_slack,
                notify_email=notify_email,
                slack_channel=slack_channel,
            )
            session.add(sch)
            session.flush()

            for idx, uid in enumerate(participants):
                sp = ScheduleParticipant(schedule_id=sch.id, user_id=uid, order_index=idx)
                session.add(sp)

            session.commit()

            # Initialize rotation state
            session.refresh(sch)
            parts = session.query(ScheduleParticipant).filter(ScheduleParticipant.schedule_id == sch.id).order_by(ScheduleParticipant.order_index.asc()).all()
            num = len(parts)
            now = now_utc()
            if num > 0:
                idx = current_rotation_index(sch.start_time_utc, sch.shift_length_minutes, now, num)
            else:
                idx = 0
            sch.current_participant_index = idx
            # compute next handoff boundary
            elapsed = (now - sch.start_time_utc).total_seconds()
            if elapsed <= 0:
                next_at = sch.start_time_utc
            else:
                shifts = int(elapsed // (sch.shift_length_minutes * 60))
                next_at = sch.start_time_utc + timedelta(minutes=sch.shift_length_minutes * (shifts + 1))
            sch.next_handoff_at_utc = next_at
            session.add(sch)
            session.commit()
            session.refresh(sch)

            return jsonify(sch.to_dict(include_participants=True)), 201
        finally:
            session.close()

    @app.get("/api/schedules")
    def list_schedules():
        session = SessionLocal()
        try:
            schedules = session.query(Schedule).order_by(Schedule.id.asc()).all()
            return jsonify([s.to_dict(include_participants=True) for s in schedules])
        finally:
            session.close()

    @app.get("/api/schedules/<int:schedule_id>")
    def get_schedule(schedule_id: int):
        session = SessionLocal()
        try:
            sch = session.get(Schedule, schedule_id)
            if not sch:
                return jsonify({"error": "not found"}), 404
            return jsonify(sch.to_dict(include_participants=True))
        finally:
            session.close()

    @app.post("/api/schedules/<int:schedule_id>/handoff")
    def force_handoff(schedule_id: int):
        session = SessionLocal()
        try:
            sch = session.get(Schedule, schedule_id)
            if not sch:
                return jsonify({"error": "not found"}), 404
            # Bring next handoff to now
            sch.next_handoff_at_utc = now_utc()
            session.add(sch)
            session.commit()
            return jsonify({"ok": True, "message": "handoff will be processed shortly"})
        finally:
            session.close()

    @app.get("/api/schedules/<int:schedule_id>/current")
    def get_current_oncall(schedule_id: int):
        session = SessionLocal()
        try:
            sch = session.get(Schedule, schedule_id)
            if not sch:
                return jsonify({"error": "not found"}), 404
            participants = session.query(ScheduleParticipant).filter(ScheduleParticipant.schedule_id == sch.id).order_by(ScheduleParticipant.order_index.asc()).all()
            num = len(participants)
            now = now_utc()
            idx = current_rotation_index(sch.start_time_utc, sch.shift_length_minutes, now, num) if num else 0
            scheduled_user = session.get(User, participants[idx].user_id) if num else None

            # apply override
            override = (
                session.query(ScheduleOverride)
                .filter(ScheduleOverride.schedule_id == sch.id)
                .filter(ScheduleOverride.start_utc <= now)
                .filter(ScheduleOverride.end_utc > now)
                .first()
            )
            current_user = session.get(User, override.user_id) if override else scheduled_user

            # next on call
            next_idx = ((idx + 1) % num) if num else None
            next_user = session.get(User, participants[next_idx].user_id) if (num and next_idx is not None) else None

            return jsonify({
                "schedule": sch.to_dict(),
                "current": current_user.to_dict() if current_user else None,
                "scheduled_current": scheduled_user.to_dict() if scheduled_user else None,
                "override": override.to_dict() if override else None,
                "next": next_user.to_dict() if next_user else None,
                "next_handoff_at_utc": sch.next_handoff_at_utc.isoformat() if sch.next_handoff_at_utc else None,
            })
        finally:
            session.close()

    @app.post("/api/schedules/<int:schedule_id>/overrides")
    def create_override(schedule_id: int):
        session = SessionLocal()
        try:
            sch = session.get(Schedule, schedule_id)
            if not sch:
                return jsonify({"error": "schedule not found"}), 404
            data = request.get_json(force=True)
            user_id = data.get("user_id")
            start = data.get("start")
            end = data.get("end")
            reason = data.get("reason")
            if not all([user_id, start, end]):
                return jsonify({"error": "user_id, start, end are required"}), 400
            start_utc = parse_dt_to_utc(start, tz_hint=sch.timezone)
            end_utc = parse_dt_to_utc(end, tz_hint=sch.timezone)
            if end_utc <= start_utc:
                return jsonify({"error": "end must be after start"}), 400
            ov = ScheduleOverride(schedule_id=schedule_id, user_id=user_id, start_utc=start_utc, end_utc=end_utc, reason=reason)
            session.add(ov)
            session.commit()
            session.refresh(ov)
            return jsonify(ov.to_dict()), 201
        finally:
            session.close()

    @app.get("/api/schedules/<int:schedule_id>/overrides")
    def list_overrides(schedule_id: int):
        session = SessionLocal()
        try:
            ovs = session.query(ScheduleOverride).filter(ScheduleOverride.schedule_id == schedule_id).order_by(ScheduleOverride.start_utc.asc()).all()
            return jsonify([o.to_dict() for o in ovs])
        finally:
            session.close()

    @app.get("/api/schedules/<int:schedule_id>/history")
    def list_history(schedule_id: int):
        session = SessionLocal()
        try:
            hist = session.query(HandoffHistory).filter(HandoffHistory.schedule_id == schedule_id).order_by(HandoffHistory.at_utc.desc()).limit(100).all()
            return jsonify([h.to_dict() for h in hist])
        finally:
            session.close()

    @app.post("/integrations/pagerduty/webhook")
    def pagerduty_webhook():
        schedule_id = request.args.get("schedule_id", type=int)
        if not schedule_id:
            return jsonify({"error": "schedule_id query param is required"}), 400
        payload = request.get_json(silent=True) or {}
        try:
            result = PagerDutyWebhook.handle_webhook(schedule_id, payload)
            status = 200 if result.get("ok") else 400
            return jsonify(result), status
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

