from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime, time as dtime, timedelta, timezone
from zoneinfo import ZoneInfo

from config import BatchWindow

_DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']


def _parse_hhmm(s: str) -> dtime:
    parts = s.split(':')
    return dtime(hour=int(parts[0]), minute=int(parts[1]))


def _day_ok(now_local: datetime, days: Optional[List[str]]) -> bool:
    if not days or len(days) == 0:
        return True
    wd = _DAYS[now_local.weekday()]
    days_norm = [d.strip().title() for d in days]
    return wd in days_norm


@dataclass
class WindowInfo:
    name: Optional[str]
    timezone: str
    start: str
    end: str
    min_gpus: int
    lead_minutes: int
    # Computed fields
    start_dt: Optional[datetime] = None


def get_active_window(now_utc: datetime, windows: List[BatchWindow]) -> Optional[WindowInfo]:
    for w in windows:
        tz = ZoneInfo(w.timezone)
        now_local = now_utc.astimezone(tz)
        if not _day_ok(now_local, w.days):
            continue
        start_t = _parse_hhmm(w.start)
        end_t = _parse_hhmm(w.end)
        start_dt = now_local.replace(hour=start_t.hour, minute=start_t.minute, second=0, microsecond=0)
        end_dt = now_local.replace(hour=end_t.hour, minute=end_t.minute, second=0, microsecond=0)
        # handle overnight
        if end_dt <= start_dt:
            # window wraps to next day
            if now_local >= start_dt or now_local < end_dt + timedelta(days=1):
                # Active either after start today or before end tomorrow
                if now_local >= start_dt:
                    pass
                else:
                    start_dt = start_dt - timedelta(days=1)
                    end_dt = end_dt
                return WindowInfo(name=w.name, timezone=w.timezone, start=w.start, end=w.end, min_gpus=w.min_gpus, lead_minutes=w.lead_minutes, start_dt=start_dt.astimezone(timezone.utc))
        else:
            if start_dt <= now_local < end_dt:
                return WindowInfo(name=w.name, timezone=w.timezone, start=w.start, end=w.end, min_gpus=w.min_gpus, lead_minutes=w.lead_minutes, start_dt=start_dt.astimezone(timezone.utc))
    return None


@dataclass
class UpcomingWindow:
    name: Optional[str]
    timezone: str
    start: str
    end: str
    min_gpus: int
    lead_minutes: int
    start_dt: Optional[datetime]


def get_next_window_start(now_utc: datetime, windows: List[BatchWindow]) -> Optional[UpcomingWindow]:
    soonest: Optional[UpcomingWindow] = None
    for w in windows:
        tz = ZoneInfo(w.timezone)
        now_local = now_utc.astimezone(tz)
        start_t = _parse_hhmm(w.start)
        start_today = now_local.replace(hour=start_t.hour, minute=start_t.minute, second=0, microsecond=0)
        # Compute next start considering days filter and overnight
        candidates = []
        for delta in range(0, 8):  # next 7 days
            cand_date = (start_today + timedelta(days=delta)).date()
            cand_dt_local = datetime.combine(cand_date, start_t, tzinfo=tz)
            if _day_ok(cand_dt_local, w.days) and cand_dt_local >= now_local:
                candidates.append(cand_dt_local)
        if not candidates:
            continue
        start_local = min(candidates)
        start_utc = start_local.astimezone(timezone.utc)
        up = UpcomingWindow(name=w.name, timezone=w.timezone, start=w.start, end=w.end, min_gpus=w.min_gpus, lead_minutes=w.lead_minutes, start_dt=start_utc)
        if soonest is None or (up.start_dt and up.start_dt < soonest.start_dt):
            soonest = up
    return soonest

