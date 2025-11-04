import threading
import time
from datetime import timedelta
from typing import Optional

from .db import SessionLocal
from .models import Schedule, ScheduleParticipant, HandoffHistory, User
from .timeutils import now_utc
from .notifications.slack import SlackNotifier
from .notifications.emailer import EmailNotifier
from .config import Config


class HandoffWorker:
    def __init__(self, interval_seconds: int = 30):
        self.interval_seconds = interval_seconds
        self._thread: Optional[threading.Thread] = None
        self._stop_ev = threading.Event()
        self._slack = SlackNotifier(Config.SLACK_BOT_TOKEN, Config.SLACK_DEFAULT_CHANNEL)
        self._email = EmailNotifier(Config.SMTP_HOST, Config.SMTP_PORT, Config.SMTP_USERNAME, Config.SMTP_PASSWORD, Config.SMTP_FROM_EMAIL, Config.SMTP_USE_TLS)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run_loop, name="HandoffWorker", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_ev.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run_loop(self):
        while not self._stop_ev.is_set():
            try:
                self._tick()
            except Exception as e:
                print(f"[HandoffWorker] Exception in tick: {e}")
            self._stop_ev.wait(self.interval_seconds)

    def _tick(self):
        session = SessionLocal()
        try:
            now = now_utc()
            schedules = session.query(Schedule).filter(Schedule.next_handoff_at_utc != None).all()  # noqa
            for sch in schedules:
                if sch.next_handoff_at_utc and sch.next_handoff_at_utc <= now:
                    self._perform_handoff(session, sch, reason="scheduled")
            session.commit()
        finally:
            session.close()

    def _perform_handoff(self, session, sch: Schedule, reason: str = ""):
        participants = session.query(ScheduleParticipant).filter(ScheduleParticipant.schedule_id == sch.id).order_by(ScheduleParticipant.order_index.asc()).all()
        if not participants:
            # nothing to do; move next handoff to future to avoid tight loop
            sch.next_handoff_at_utc = now_utc() + timedelta(minutes=sch.shift_length_minutes)
            session.add(sch)
            return
        # Determine from/to
        from_idx = sch.current_participant_index % len(participants)
        to_idx = (sch.current_participant_index + 1) % len(participants)
        from_user_id = participants[from_idx].user_id if 0 <= from_idx < len(participants) else None
        to_user_id = participants[to_idx].user_id if 0 <= to_idx < len(participants) else None

        hist = HandoffHistory(schedule_id=sch.id, from_user_id=from_user_id, to_user_id=to_user_id, at_utc=sch.next_handoff_at_utc or now_utc(), reason=reason)
        session.add(hist)

        # Advance schedule
        sch.current_participant_index = to_idx
        if sch.next_handoff_at_utc is None:
            sch.next_handoff_at_utc = now_utc() + timedelta(minutes=sch.shift_length_minutes)
        else:
            sch.next_handoff_at_utc = sch.next_handoff_at_utc + timedelta(minutes=sch.shift_length_minutes)
        session.add(sch)

        # Notifications
        self._notify(session, sch, from_user_id, to_user_id)

    def _notify(self, session, sch: Schedule, from_user_id: Optional[int], to_user_id: Optional[int]):
        from_user = session.get(User, from_user_id) if from_user_id else None
        to_user = session.get(User, to_user_id) if to_user_id else None
        tz = sch.timezone
        when = sch.next_handoff_at_utc  # this is already advanced, but ok for message
        text = f"[On-Call Handoff] Schedule '{sch.name}' -> {from_user.name if from_user else 'N/A'} to {to_user.name if to_user else 'N/A'} at {when} ({tz})"

        if sch.notify_slack:
            self._slack.send_message(text=text, channel=sch.slack_channel)

        if sch.notify_email:
            recipients = []
            if from_user and from_user.email:
                recipients.append(from_user.email)
            if to_user and to_user.email:
                recipients.append(to_user.email)
            if recipients:
                self._email.send(recipients, subject=f"Handoff: {sch.name}", body=text)

