from datetime import date, datetime, timedelta
import pandas as pd


def parse_date(d):
    if isinstance(d, date) and not isinstance(d, datetime):
        return d
    if isinstance(d, datetime):
        return d.date()
    # Expecting YYYY-MM-DD
    return datetime.fromisoformat(str(d)).date()


def period_floor(d: date, period: str) -> date:
    if period == 'daily':
        return d
    elif period == 'weekly':
        # ISO week starts Monday
        return (d - timedelta(days=d.weekday()))
    elif period == 'monthly':
        return date(d.year, d.month, 1)
    else:
        raise ValueError('Invalid period')


def period_key_sorter(item):
    # item is (iso_date_str, value)
    return (item[0],)


def freq_for_period(period: str) -> str:
    if period == 'daily':
        return 'D'
    if period == 'weekly':
        return 'W-MON'
    if period == 'monthly':
        return 'MS'
    raise ValueError('Invalid period')


def build_full_period_index(start: date, end: date, freq: str) -> pd.DatetimeIndex:
    if start is None or end is None:
        return pd.DatetimeIndex([])
    start_dt = pd.to_datetime(start)
    end_dt = pd.to_datetime(end)
    return pd.date_range(start=start_dt, end=end_dt, freq=freq)

