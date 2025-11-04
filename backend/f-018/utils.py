from datetime import datetime, timedelta, date
from statistics import median
from typing import Iterable, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    from backports.zoneinfo import ZoneInfo  # type: ignore


def safe_float(v, default: float = None) -> Optional[float]:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def parse_ts_to_utc(ts: str) -> datetime:
    # Accept 'Z' suffix or offset-aware ISO
    s = ts.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        # assume UTC if naive
        return dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(ZoneInfo("UTC"))


def as_date(s: str) -> Optional[date]:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def day_bounds_utc(d: date, tzname: str) -> Tuple[datetime, datetime]:
    tz = None
    try:
        tz = ZoneInfo(tzname)
    except Exception:
        tz = ZoneInfo("UTC")
    start_local = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(ZoneInfo("UTC"))
    end_utc = end_local.astimezone(ZoneInfo("UTC"))
    return start_utc, end_utc


def utc_to_local_date(dt_utc: datetime, tzname: str = "UTC") -> date:
    tz = None
    try:
        tz = ZoneInfo(tzname)
    except Exception:
        tz = ZoneInfo("UTC")
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=ZoneInfo("UTC"))
    return dt_utc.astimezone(tz).date()


def compute_p95(values: Iterable[float]) -> Optional[float]:
    vals = sorted([float(v) for v in values if v is not None])
    n = len(vals)
    if n == 0:
        return None
    # Nearest-rank method
    rank = int(0.95 * (n - 1))
    return vals[rank]

