from datetime import datetime
from typing import Any, Optional


def to_epoch_seconds(ts: Any) -> Optional[int]:
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        return int(ts)
    if isinstance(ts, str):
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return int(dt.timestamp())
        except Exception:
            try:
                return int(float(ts))
            except Exception:
                return None
    return None

