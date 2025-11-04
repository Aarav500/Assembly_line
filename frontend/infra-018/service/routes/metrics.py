from datetime import datetime, timedelta
from typing import List, Dict

from dateutil import parser as dateparser
from flask import Blueprint, request, jsonify
from sqlalchemy import select, func, text, cast, String, and_, or_, case

from ..db import db_session
from ..models import Event

bp = Blueprint("metrics", __name__)


VALID_INTERVALS = {"hour", "day", "week", "month"}


def parse_iso_dt(v, default=None):
    if not v:
        return default
    try:
        return dateparser.isoparse(v)
    except Exception:
        return default


def interval_trunc(interval: str, col):
    return func.date_trunc(interval, col)


@bp.route("/metrics/events", methods=["GET"])
def metrics_events_timeseries():
    name = request.args.get("name")
    if not name:
        return jsonify({"error": "Missing 'name' parameter"}), 400
    start = parse_iso_dt(request.args.get("start"))
    end = parse_iso_dt(request.args.get("end"))
    if not start or not end:
        return jsonify({"error": "'start' and 'end' must be ISO datetimes"}), 400
    interval = request.args.get("interval", "day").lower()
    if interval not in VALID_INTERVALS:
        return jsonify({"error": f"Invalid interval. Choose from {sorted(VALID_INTERVALS)}"}), 400

    bucket = interval_trunc(interval, Event.event_time).label("bucket")

    stmt = (
        select(bucket, func.count().label("count"))
        .where(and_(Event.name == name, Event.event_time >= start, Event.event_time <= end))
        .group_by(bucket)
        .order_by(bucket)
    )
    rows = db_session.execute(stmt).all()
    data = [{"bucket": r.bucket.isoformat(), "count": int(r.count)} for r in rows]
    return jsonify({"series": data, "name": name, "interval": interval})


@bp.route("/metrics/active-users", methods=["GET"])
def metrics_active_users():
    start = parse_iso_dt(request.args.get("start"))
    end = parse_iso_dt(request.args.get("end"))
    if not start or not end:
        return jsonify({"error": "'start' and 'end' must be ISO datetimes"}), 400
    interval = request.args.get("interval", "day").lower()
    if interval not in VALID_INTERVALS:
        return jsonify({"error": f"Invalid interval. Choose from {sorted(VALID_INTERVALS)}"}), 400

    user_key = func.coalesce(cast(Event.user_id, String), Event.anonymous_id)
    bucket = interval_trunc(interval, Event.event_time).label("bucket")

    stmt = (
        select(bucket, func.count(func.distinct(user_key)).label("active_users"))
        .where(and_(Event.event_time >= start, Event.event_time <= end))
        .group_by(bucket)
        .order_by(bucket)
    )
    rows = db_session.execute(stmt).all()
    data = [{"bucket": r.bucket.isoformat(), "active_users": int(r.active_users)} for r in rows]
    return jsonify({"series": data, "interval": interval})


@bp.route("/metrics/funnel", methods=["GET"])
def metrics_funnel():
    steps_param = request.args.get("steps")
    if not steps_param:
        return jsonify({"error": "Missing 'steps' parameter (comma-separated event names)"}), 400
    steps = [s.strip() for s in steps_param.split(",") if s.strip()]
    if len(steps) < 2:
        return jsonify({"error": "At least two steps are required"}), 400

    start = parse_iso_dt(request.args.get("start"))
    end = parse_iso_dt(request.args.get("end"))
    if not start or not end:
        return jsonify({"error": "'start' and 'end' must be ISO datetimes"}), 400

    user_key = func.coalesce(cast(Event.user_id, String), Event.anonymous_id).label("user_key")

    # Get events for users who performed step 1 in the window
    first_step = steps[0]
    sub = (
        select(user_key.label("uk"), Event.event_time.label("t"))
        .where(and_(Event.name == first_step, Event.event_time >= start, Event.event_time <= end))
    ).subquery()

    # Pull all relevant events for users in subquery within the time window (for simplicity, we enforce <= end)
    stmt = (
        select(user_key, Event.name, Event.event_time)
        .where(
            and_(
                Event.name.in_(steps),
                Event.event_time >= start,
                Event.event_time <= end,
                user_key.in_(select(sub.c.uk)),
            )
        )
        .order_by(user_key, Event.event_time)
    )
    rows = db_session.execute(stmt).all()

    # Build funnel per user
    counts = [0] * len(steps)
    per_user_reached = {}

    current_user = None
    reached_idx = 0

    def finalize_user(uk, reached):
        if uk is None:
            return
        if uk not in per_user_reached:
            per_user_reached[uk] = [False] * len(steps)
        for i in range(reached):
            per_user_reached[uk][i] = True

    last_time_by_user = {}

    for r in rows:
        uk = r.user_key
        ename = r.name
        etime = r.event_time
        if uk != current_user:
            # finalize previous
            finalize_user(current_user, reached_idx)
            current_user = uk
            reached_idx = 0
            last_time_by_user[uk] = None
        # Enforce sequence
        if ename == steps[reached_idx]:
            # If time must be increasing, ensure etime >= last time
            if last_time_by_user[uk] is None or etime >= last_time_by_user[uk]:
                reached_idx += 1
                last_time_by_user[uk] = etime
                if reached_idx == len(steps):
                    # user completed funnel; continue to ensure finalize later
                    pass
        # For users who have already reached final step, we just keep ignoring further
    # finalize last user
    finalize_user(current_user, reached_idx)

    # Aggregate counts
    for flags in per_user_reached.values():
        for i, ok in enumerate(flags):
            if ok:
                counts[i] += 1

    total_at_step1 = counts[0]
    conversion = []
    cumulative_rate = []
    for i, c in enumerate(counts):
        conversion.append({"step": steps[i], "count": c})
        rate = (c / total_at_step1) if total_at_step1 > 0 else 0.0
        cumulative_rate.append({"step": steps[i], "rate": round(rate, 4)})

    return jsonify({
        "steps": steps,
        "counts": conversion,
        "rates": cumulative_rate,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "total_users_step1": total_at_step1,
    })


@bp.route("/metrics/retention", methods=["GET"])
def metrics_retention():
    event_name = request.args.get("event")
    if not event_name:
        return jsonify({"error": "Missing 'event' parameter"}), 400

    period = request.args.get("period", "weekly").lower()
    if period not in {"daily", "weekly", "monthly"}:
        return jsonify({"error": "period must be one of daily, weekly, monthly"}), 400

    start = parse_iso_dt(request.args.get("start"))
    end = parse_iso_dt(request.args.get("end"))
    if not start or not end:
        return jsonify({"error": "'start' and 'end' must be ISO datetimes"}), 400

    user_key = func.coalesce(cast(Event.user_id, String), Event.anonymous_id).label("user_key")
    trunc = {
        "daily": "day",
        "weekly": "week",
        "monthly": "month",
    }[period]

    # Base cohort: users whose first occurrence of the event within window
    bucket = func.date_trunc(trunc, Event.event_time).label("bucket")

    firsts_stmt = (
        select(user_key, func.min(Event.event_time).label("first_time"))
        .where(and_(Event.name == event_name, Event.event_time >= start, Event.event_time <= end))
        .group_by(user_key)
    ).subquery()

    cohort_stmt = select(firsts_stmt.c.user_key, func.date_trunc(trunc, firsts_stmt.c.first_time).label("cohort"))
    cohort_rows = db_session.execute(cohort_stmt).all()

    if not cohort_rows:
        return jsonify({"cohorts": [], "period": period, "event": event_name})

    # Build cohort sets
    cohorts = {}
    for r in cohort_rows:
        key = (r.cohort).isoformat()
        cohorts.setdefault(key, set()).add(r.user_key)

    # Determine number of periods to check (up to 12)
    max_periods = 12

    # Fetch all events for these users within end + window for retention calculation
    all_users = set()
    for s in cohorts.values():
        all_users.update(s)
    users_list = list(all_users)

    events_stmt = (
        select(user_key, Event.event_time)
        .where(and_(Event.name == event_name, user_key.in_(users_list)))
        .order_by(user_key, Event.event_time)
    )
    events_rows = db_session.execute(events_stmt).all()

    # Group events per user by bucket index offset from cohort start
    from collections import defaultdict

    user_events_by_bucket = defaultdict(set)  # user_key -> set of bucket timestamps

    def bucket_start(dt: datetime):
        return db_session.execute(select(func.date_trunc(trunc, func.cast(text(f"timestamp '{dt.isoformat()}'"), DateTime)))).scalar_one()

    # Pre-compute buckets for all event times per user
    for r in events_rows:
        uk = r.user_key
        # Determine bucket for this event
        b = db_session.execute(select(func.date_trunc(trunc, func.cast(text(f"timestamp '{r.event_time.isoformat()}'"), DateTime)))).scalar_one()
        user_events_by_bucket[uk].add(b)

    # Build results
    results = []
    for cohort_label, users in sorted(cohorts.items()):
        cohort_dt = dateparser.isoparse(cohort_label)
        # Build subsequent bucket datetimes
        buckets = []
        cur = cohort_dt
        for i in range(max_periods + 1):
            buckets.append(cur)
            if period == "daily":
                cur = cur + timedelta(days=1)
            elif period == "weekly":
                cur = cur + timedelta(weeks=1)
            else:
                # month approx by adding 32 days then trunc
                cur = (cur + timedelta(days=32)).replace(day=1)
        size = len(users)
        retention_counts = {}
        for i in range(1, max_periods + 1):
            b = buckets[i]
            count = 0
            for u in users:
                if b in user_events_by_bucket.get(u, set()):
                    count += 1
            retention_counts[str(i)] = count
        results.append({
            "cohort": cohort_label,
            "size": size,
            "retention": retention_counts,
        })

    return jsonify({"cohorts": results, "period": period, "event": event_name})


@bp.route("/reports/summary", methods=["GET"])
def report_summary():
    # Time range
    end = parse_iso_dt(request.args.get("end")) or datetime.utcnow()
    start = parse_iso_dt(request.args.get("start")) or (end - timedelta(days=7))

    # Top events
    top_stmt = (
        select(Event.name, func.count().label("count"))
        .where(and_(Event.event_time >= start, Event.event_time <= end))
        .group_by(Event.name)
        .order_by(func.count().desc())
        .limit(10)
    )
    top_rows = db_session.execute(top_stmt).all()

    # DAU last 7 days
    user_key = func.coalesce(cast(Event.user_id, String), Event.anonymous_id)
    dau_stmt = (
        select(func.date_trunc("day", Event.event_time).label("bucket"), func.count(func.distinct(user_key)).label("active"))
        .where(Event.event_time >= (end - timedelta(days=7)))
        .group_by(func.date_trunc("day", Event.event_time))
        .order_by(func.date_trunc("day", Event.event_time))
    )
    dau_rows = db_session.execute(dau_stmt).all()

    return jsonify({
        "top_events": [{"name": r.name, "count": int(r.count)} for r in top_rows],
        "active_users_daily": [{"bucket": r.bucket.isoformat(), "active": int(r.active)} for r in dau_rows],
        "start": start.isoformat(),
        "end": end.isoformat(),
    })

