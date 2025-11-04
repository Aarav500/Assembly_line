from __future__ import annotations
from datetime import datetime, timezone, timedelta
from dateutil import parser
from zoneinfo import ZoneInfo


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_dt_to_utc(dt_str: str, tz_hint: str | None = None) -> datetime:
    # Parse ISO8601; if naive, assume tz_hint or UTC
    dt = parser.isoparse(dt_str)
    if dt.tzinfo is None:
        tz = ZoneInfo(tz_hint) if tz_hint else timezone.utc
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(timezone.utc)


def to_tz(dt: datetime, tz_name: str) -> datetime:
    return dt.astimezone(ZoneInfo(tz_name))


def ceil_next_boundary(start_utc: datetime, shift_minutes: int, ref_utc: datetime) -> tuple[int, datetime]:
    # Returns (rotation_index, next_handoff_at_utc)
    if ref_utc <= start_utc:
        return (0, start_utc)
    delta: timedelta = ref_utc - start_utc
    shift = timedelta(minutes=shift_minutes)
    passed = int(delta.total_seconds() // shift.total_seconds())
    next_boundary = start_utc + shift * (passed + 1)
    return ((passed + 0) % (10**12), next_boundary)  # index based on passed intervals since start


def current_rotation_index(start_utc: datetime, shift_minutes: int, ref_utc: datetime, num_participants: int) -> int:
    if num_participants <= 0:
        return 0
    if ref_utc < start_utc:
        return 0
    delta = ref_utc - start_utc
    shifts = int(delta.total_seconds() // (shift_minutes * 60))
    return shifts % num_participants

