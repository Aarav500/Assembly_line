from __future__ import annotations
from datetime import datetime, timedelta, time as dtime
from typing import Any, Dict, List, Optional, Tuple

import pytz
from dateutil import tz
from flask import current_app

from ..extensions import db
from ..models import NotificationEvent, NotificationPreferences, User
from ..providers.email import EmailProvider
from ..providers.sms import SMSProvider
from ..providers.push import PushProvider


VALID_CHANNELS = {"email", "sms", "push"}
VALID_FREQUENCIES = {"immediate", "daily", "weekly"}


class NotificationService:
    def __init__(self):
        self.email_provider = EmailProvider()
        self.sms_provider = SMSProvider()
        self.push_provider = PushProvider()

    # User and preferences helpers
    def get_or_create_user(self, user_id: Optional[int] = None, **kwargs) -> User:
        user: Optional[User] = None
        if user_id is not None:
            user = User.query.get(user_id)
        if user is None:
            # Create a minimal user with provided kwargs
            tz_name = kwargs.get("timezone") or current_app.config.get("DEFAULT_TIMEZONE", "UTC")
            user = User(
                email=kwargs.get("email"),
                phone=kwargs.get("phone"),
                push_token=kwargs.get("push_token"),
                timezone=tz_name,
            )
            db.session.add(user)
            db.session.flush()
        return user

    def get_or_create_preferences(self, user: User) -> NotificationPreferences:
        prefs: Optional[NotificationPreferences] = NotificationPreferences.query.filter_by(user_id=user.id).first()
        if prefs is None:
            prefs = NotificationPreferences(user_id=user.id)
            db.session.add(prefs)
            db.session.flush()
        return prefs

    # Preference serialization/validation
    def serialize_preferences(self, prefs: NotificationPreferences) -> Dict[str, Any]:
        return {
            "userId": prefs.user_id,
            "channels": {
                "email": prefs.email_enabled,
                "sms": prefs.sms_enabled,
                "push": prefs.push_enabled,
            },
            "frequency": prefs.frequency,
            "digest": {
                "enabled": prefs.digest_enabled,
                "timeLocal": prefs.digest_time_local.isoformat() if prefs.digest_time_local else None,
                "weekday": prefs.digest_weekday,
                "lastSentAt": prefs.last_digest_sent_at.isoformat() if prefs.last_digest_sent_at else None,
            },
            "categories": prefs.categories or {},
        }

    def update_preferences(self, user: User, payload: Dict[str, Any]) -> NotificationPreferences:
        prefs = self.get_or_create_preferences(user)

        channels = payload.get("channels") or {}
        if "email" in channels:
            prefs.email_enabled = bool(channels["email"])
        if "sms" in channels:
            prefs.sms_enabled = bool(channels["sms"])
        if "push" in channels:
            prefs.push_enabled = bool(channels["push"])

        freq = payload.get("frequency")
        if freq:
            if freq not in VALID_FREQUENCIES:
                raise ValueError("Invalid frequency. Use one of: immediate, daily, weekly")
            prefs.frequency = freq

        digest = payload.get("digest") or {}
        if "enabled" in digest:
            prefs.digest_enabled = bool(digest["enabled"])
        if "timeLocal" in digest:
            t = digest["timeLocal"]
            if t is None:
                prefs.digest_time_local = None
            else:
                prefs.digest_time_local = self._parse_hhmm(t)
        if "weekday" in digest:
            wd = digest["weekday"]
            if wd is None:
                prefs.digest_weekday = None
            else:
                if not isinstance(wd, int) or wd < 0 or wd > 6:
                    raise ValueError("weekday must be integer 0-6 (Mon=0 .. Sun=6)")
                prefs.digest_weekday = wd

        if "categories" in payload and isinstance(payload["categories"], dict):
            # Validate category entries
            new_cats = {}
            for cat, cfg in (payload["categories"] or {}).items():
                if not isinstance(cfg, dict):
                    continue
                entry = {}
                for ch in ("email", "sms", "push"):
                    if ch in cfg:
                        entry[ch] = bool(cfg[ch])
                if "digest" in cfg:
                    entry["digest"] = bool(cfg["digest"])
                new_cats[cat] = entry
            prefs.categories = new_cats

        db.session.add(prefs)
        db.session.commit()
        return prefs

    # Event recording and sending
    def record_event(
        self,
        user_id: int,
        category: str,
        message: str,
        channels: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        user = User.query.get(user_id)
        if not user:
            raise ValueError("User not found")
        prefs = self.get_or_create_preferences(user)

        channels = channels or ["email", "sms", "push"]
        channels = [c for c in channels if c in VALID_CHANNELS]

        category_cfg = (prefs.categories or {}).get(category, {})
        category_digest = bool(category_cfg.get("digest", False))

        # Decide per channel whether to send immediately or include in digest
        deliver_channels_immediate: List[str] = []
        include_in_digest = False

        for ch in channels:
            if not self._channel_enabled(prefs, category_cfg, ch):
                continue
            # If category says digest, then queue for digest; else follow global frequency
            if category_digest or (prefs.frequency in {"daily", "weekly"} and prefs.digest_enabled):
                include_in_digest = True
            else:
                deliver_channels_immediate.append(ch)

        ev = NotificationEvent(
            user_id=user.id,
            category=category,
            message=message,
            channels=channels,
            in_digest=include_in_digest,
        )
        db.session.add(ev)
        db.session.flush()

        sent_channels: List[str] = []
        if deliver_channels_immediate:
            sent_channels = self._send_channels_immediately(user, prefs, deliver_channels_immediate, subject=f"Notification: {category}", body=message)
            ev.delivered = include_in_digest is False  # delivered only if not also in digest
            if sent_channels:
                ev.delivered_channels = sent_channels
            ev.delivered_at = datetime.utcnow()

        db.session.commit()
        return {
            "eventId": ev.id,
            "queuedForDigest": include_in_digest,
            "sentChannels": sent_channels,
        }

    # Digest processing
    def run_due_digests(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        now_utc = datetime.utcnow()
        users_q = User.query
        if user_id is not None:
            users_q = users_q.filter(User.id == user_id)
        users = users_q.all()

        processed: List[int] = []
        skipped: Dict[int, str] = {}

        for user in users:
            prefs = self.get_or_create_preferences(user)
            if not prefs.digest_enabled or prefs.frequency not in {"daily", "weekly"}:
                skipped[user.id] = "Digest disabled or frequency immediate"
                continue

            if not prefs.digest_time_local:
                skipped[user.id] = "No digest_time_local configured"
                continue

            due, scheduled_dt_utc = self._is_digest_due(user, prefs, now_utc)
            if not due:
                skipped[user.id] = "Not due"
                continue

            # Collect pending digest events
            pending = (
                NotificationEvent.query
                .filter_by(user_id=user.id, in_digest=True, delivered=False)
                .order_by(NotificationEvent.created_at.asc())
                .all()
            )
            if not pending:
                # Even if no events, update last_digest_sent_at to avoid constant re-trigger
                prefs.last_digest_sent_at = scheduled_dt_utc
                db.session.add(prefs)
                db.session.commit()
                skipped[user.id] = "No pending events"
                continue

            # Build digest content
            grouped: Dict[str, List[str]] = {}
            for ev in pending:
                grouped.setdefault(ev.category, []).append(ev.message)

            subject = f"Your {prefs.frequency} digest"
            body = self._format_digest_body(grouped)

            sent_channels = self._send_digest_to_enabled_channels(user, prefs, subject, body)

            # Mark events delivered
            for ev in pending:
                ev.delivered = True
                ev.delivered_channels = sent_channels
                ev.delivered_at = now_utc
                db.session.add(ev)

            prefs.last_digest_sent_at = scheduled_dt_utc
            db.session.add(prefs)
            db.session.commit()

            processed.append(user.id)

        return {"processedUserIds": processed, "skipped": skipped}

    def preview_digest(self, user_id: int) -> Dict[str, Any]:
        user = User.query.get(user_id)
        if not user:
            raise ValueError("User not found")
        pending = (
            NotificationEvent.query
            .filter_by(user_id=user.id, in_digest=True, delivered=False)
            .order_by(NotificationEvent.created_at.asc())
            .all()
        )
        grouped: Dict[str, List[str]] = {}
        for ev in pending:
            grouped.setdefault(ev.category, []).append(ev.message)
        return {"userId": user.id, "groups": grouped, "preview": self._format_digest_body(grouped)}

    # Internal helpers
    def _parse_hhmm(self, s: str) -> dtime:
        # Accept HH:MM or HH:MM:SS
        try:
            parts = [int(p) for p in s.split(":")]
            if len(parts) == 2:
                return dtime(parts[0], parts[1])
            if len(parts) == 3:
                return dtime(parts[0], parts[1], parts[2])
        except Exception as e:
            raise ValueError("Invalid time format. Use HH:MM or HH:MM:SS") from e
        raise ValueError("Invalid time format. Use HH:MM or HH:MM:SS")

    def _channel_enabled(self, prefs: NotificationPreferences, category_cfg: Dict[str, Any], channel: str) -> bool:
        base = {
            "email": prefs.email_enabled,
            "sms": prefs.sms_enabled,
            "push": prefs.push_enabled,
        }[channel]
        if category_cfg is None:
            return base
        if channel in category_cfg:
            return base and bool(category_cfg[channel])
        return base

    def _send_channels_immediately(
        self,
        user: User,
        prefs: NotificationPreferences,
        channels: List[str],
        subject: str,
        body: str,
    ) -> List[str]:
        sent: List[str] = []
        for ch in channels:
            if ch == "email" and prefs.email_enabled and user.email:
                if self.email_provider.send(user.email, subject, body):
                    sent.append("email")
            elif ch == "sms" and prefs.sms_enabled and user.phone:
                if self.sms_provider.send(user.phone, body):
                    sent.append("sms")
            elif ch == "push" and prefs.push_enabled and user.push_token:
                if self.push_provider.send(user.push_token, subject, body):
                    sent.append("push")
        return sent

    def _send_digest_to_enabled_channels(self, user: User, prefs: NotificationPreferences, subject: str, body: str) -> List[str]:
        sent: List[str] = []
        # Respect per-category channel overrides for digest? Using overall channel toggles here.
        if prefs.email_enabled and user.email:
            if self.email_provider.send(user.email, subject, body):
                sent.append("email")
        if prefs.sms_enabled and user.phone:
            if self.sms_provider.send(user.phone, body):
                sent.append("sms")
        if prefs.push_enabled and user.push_token:
            if self.push_provider.send(user.push_token, subject, body):
                sent.append("push")
        return sent

    def _format_digest_body(self, grouped: Dict[str, List[str]]) -> str:
        lines: List[str] = []
        for cat, msgs in grouped.items():
            lines.append(f"Category: {cat}")
            for m in msgs:
                lines.append(f" - {m}")
            lines.append("")
        if not lines:
            return "No new items."
        return "\n".join(lines).strip()

    def _is_digest_due(self, user: User, prefs: NotificationPreferences, now_utc: datetime) -> Tuple[bool, datetime]:
        tz_name = user.timezone or current_app.config.get("DEFAULT_TIMEZONE", "UTC")
        try:
            tzinfo = pytz.timezone(tz_name)
        except Exception:
            tzinfo = pytz.UTC

        now_local = now_utc.astimezone(tzinfo)
        digest_time: dtime = prefs.digest_time_local
        if digest_time is None:
            # default 09:00
            digest_time = dtime(9, 0)

        if prefs.frequency == "daily":
            scheduled_local = now_local.replace(hour=digest_time.hour, minute=digest_time.minute, second=digest_time.second, microsecond=0)
            if scheduled_local > now_local:
                # Today not yet reached, consider yesterday's schedule
                scheduled_local = scheduled_local - timedelta(days=1)
        elif prefs.frequency == "weekly":
            wd = prefs.digest_weekday if prefs.digest_weekday is not None else 0
            # Find the most recent weekday occurrence at digest_time
            days_back = (now_local.weekday() - wd) % 7
            scheduled_local = now_local - timedelta(days=days_back)
            scheduled_local = scheduled_local.replace(hour=digest_time.hour, minute=digest_time.minute, second=digest_time.second, microsecond=0)
            if scheduled_local > now_local:
                scheduled_local = scheduled_local - timedelta(days=7)
        else:
            # Immediate frequency does not schedule digest
            return (False, now_utc)

        scheduled_utc = scheduled_local.astimezone(pytz.UTC)

        last = prefs.last_digest_sent_at
        if last is None:
            # If never sent, due if we are past the scheduled time
            return (now_utc >= scheduled_utc, scheduled_utc)
        else:
            return (last < scheduled_utc <= now_utc, scheduled_utc)


service = NotificationService()

