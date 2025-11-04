from datetime import datetime
from dateutil import parser


def parse_time(s):
    if not s:
        return None
    try:
        dt = parser.isoparse(s)
        if not dt.tzinfo:
            return dt
        return dt.astimezone(tz=None).replace(tzinfo=None)
    except Exception:
        try:
            return datetime.utcfromtimestamp(float(s))
        except Exception:
            return None

