from datetime import datetime, timedelta


def month_add(dt: datetime, months: int) -> datetime:
    # Add months preserving day with clamping
    year = dt.year + (dt.month - 1 + months) // 12
    month = (dt.month - 1 + months) % 12 + 1
    day = dt.day
    # handle end-of-month
    for _ in range(3):
        try:
            return dt.replace(year=year, month=month, day=day)
        except ValueError:
            day -= 1
    return dt.replace(year=year, month=month, day=1)


def billing_period_containing(now: datetime, anchor_day: int) -> tuple[datetime, datetime]:
    # Construct the start of the period that contains 'now' based on anchor day-of-month
    # Anchor_day is between 1 and 28 ideally
    # Determine the most recent date with day == anchor_day that is <= now
    start_candidate = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if now.day >= anchor_day:
        start = start_candidate.replace(day=anchor_day)
    else:
        # previous month
        prev_month = month_add(start_candidate, -1)
        start = prev_month.replace(day=anchor_day)
    end = month_add(start, 1)
    return (start, end)


def last_completed_billing_period(now: datetime, anchor_day: int) -> tuple[datetime, datetime]:
    current_start, _ = billing_period_containing(now, anchor_day)
    prev_end = current_start
    prev_start = month_add(prev_end, -1)
    return (prev_start, prev_end)

