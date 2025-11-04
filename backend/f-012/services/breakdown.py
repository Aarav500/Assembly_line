from collections import defaultdict
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from models import CostRecord
from utils.time import period_floor, period_key_sorter


UNTAGGED = "__untagged__"


def get_breakdown(session: Session, group_by: Optional[str], period: str, start=None, end=None) -> Dict[str, Any]:
    period = (period or "daily").lower()
    if period not in ("daily", "weekly", "monthly"):
        raise ValueError("period must be one of daily, weekly, monthly")

    q = session.query(CostRecord)
    if start is not None:
        q = q.filter(CostRecord.date >= start)
    if end is not None:
        q = q.filter(CostRecord.date <= end)

    bucketed: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    totals: Dict[str, float] = defaultdict(float)

    for rec in q:
        tag_val = UNTAGGED
        if group_by:
            t = rec.tags or {}
            tag_val = str(t.get(group_by, UNTAGGED))
        period_start = period_floor(rec.date, period)
        pkey = period_start.isoformat()
        bucketed[tag_val][pkey] += float(rec.amount)
        totals[tag_val] += float(rec.amount)

    # Compose response
    groups = []
    for tag_val, series_map in bucketed.items():
        # order series by period key
        series_items = sorted(series_map.items(), key=period_key_sorter)
        series = [{"period": k, "amount": round(v, 6)} for k, v in series_items]
        groups.append({
            "tag_value": tag_val,
            "series": series,
            "total": round(totals.get(tag_val, 0.0), 6)
        })

    # sort groups by total desc
    groups.sort(key=lambda g: g["total"], reverse=True)

    return {
        "group_by": group_by,
        "period": period,
        "data": groups,
    }

