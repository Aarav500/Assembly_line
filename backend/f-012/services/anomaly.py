from typing import Dict, Any, Optional, List
from collections import defaultdict
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session

from models import CostRecord
from utils.time import period_floor, freq_for_period, build_full_period_index

UNTAGGED = "__untagged__"


def aggregate_series(session: Session, group_by: str, period: str, start=None, end=None):
    q = session.query(CostRecord)
    if start is not None:
        q = q.filter(CostRecord.date >= start)
    if end is not None:
        q = q.filter(CostRecord.date <= end)

    data = defaultdict(lambda: defaultdict(float))  # tag_value -> period_date_str -> amount

    min_date = None
    max_date = None

    for rec in q:
        tval = str((rec.tags or {}).get(group_by, UNTAGGED))
        pdate = period_floor(rec.date, period)
        pkey = pdate.isoformat()
        data[tval][pkey] += float(rec.amount)
        if min_date is None or pdate < min_date:
            min_date = pdate
        if max_date is None or pdate > max_date:
            max_date = pdate

    freq = freq_for_period(period)
    full_index = build_full_period_index(min_date, max_date, freq) if (min_date and max_date) else pd.DatetimeIndex([])

    series_by_group = {}
    for tval, m in data.items():
        s = pd.Series(m, dtype=float)
        s.index = pd.to_datetime(s.index)
        if len(full_index) > 0:
            s = s.reindex(full_index, fill_value=0.0)
        s.sort_index(inplace=True)
        series_by_group[tval] = s

    return series_by_group, freq


def rolling_zscore(series: pd.Series, window: int) -> pd.Series:
    if window <= 1:
        mu = series.rolling(window=2, min_periods=2).mean()
        sigma = series.rolling(window=2, min_periods=2).std(ddof=0)
    else:
        mu = series.rolling(window=window, min_periods=window).mean()
        sigma = series.rolling(window=window, min_periods=window).std(ddof=0)
    z = pd.Series(np.zeros(len(series)), index=series.index, dtype=float)
    with np.errstate(divide='ignore', invalid='ignore'):
        z = (series - mu) / sigma
    z = z.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return z


def rolling_mad_score(series: pd.Series, window: int) -> pd.Series:
    # Median Absolute Deviation based robust z-score
    med = series.rolling(window=window, min_periods=window).median()
    mad = (series.rolling(window=window, min_periods=window)
           .apply(lambda x: np.median(np.abs(x - np.median(x))), raw=True))
    # constant to make it comparable to std for normal distributions
    const = 0.6745
    with np.errstate(divide='ignore', invalid='ignore'):
        score = const * (series - med) / mad
    score = pd.Series(score, index=series.index)
    score = score.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return score


def detect_anomalies(session: Session,
                     group_by: str,
                     period: str,
                     start=None,
                     end=None,
                     method: str = "zscore",
                     threshold: float = 3.0,
                     window: int = 7,
                     min_points: int = 14,
                     direction: str = "both") -> Dict[str, Any]:
    period = (period or "daily").lower()
    if period not in ("daily", "weekly", "monthly"):
        raise ValueError("period must be one of daily, weekly, monthly")

    method = (method or "zscore").lower()
    if method not in ("zscore", "mad"):
        raise ValueError("method must be 'zscore' or 'mad'")

    if direction not in ("up", "down", "both"):
        raise ValueError("direction must be one of up, down, both")

    series_by_group, freq = aggregate_series(session, group_by, period, start, end)

    anomalies: List[Dict[str, Any]] = []

    for tag_val, s in series_by_group.items():
        if len(s) < max(min_points, window):
            continue
        if method == "zscore":
            score = rolling_zscore(s, window)
        else:
            score = rolling_mad_score(s, window)

        if direction == "up":
            mask = score >= threshold
        elif direction == "down":
            mask = score <= -threshold
        else:
            mask = score.abs() >= threshold

        idxs = s.index[mask]
        for idx in idxs:
            anomalies.append({
                "tag_value": tag_val,
                "period": idx.date().isoformat(),
                "amount": round(float(s.loc[idx]), 6),
                "score": round(float(score.loc[idx]), 6),
                "method": method
            })

    # sort anomalies by absolute score desc
    anomalies.sort(key=lambda a: abs(a["score"]), reverse=True)

    return {
        "group_by": group_by,
        "period": period,
        "method": method,
        "params": {
            "threshold": threshold,
            "window": window,
            "min_points": min_points,
            "direction": direction
        },
        "anomalies": anomalies
    }

