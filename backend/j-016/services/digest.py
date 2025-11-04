from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
import pytz
from db import db
from models import Team, Route, Event
from services.routing import matches_filters
from services.delivery import queue_delivery


def _now_utc() -> datetime:
    return datetime.utcnow().replace(tzinfo=pytz.utc)


def _team_now(team: Team) -> datetime:
    tz = pytz.timezone(team.timezone or 'UTC')
    return datetime.now(tz)


def _frequency_delta(freq: str) -> timedelta:
    if freq == 'hourly':
        return timedelta(hours=1)
    if freq == 'daily':
        return timedelta(days=1)
    return timedelta(hours=1)


def should_run_digest(team: Team, now_utc: datetime) -> bool:
    if not team.digest_enabled:
        return False
    freq = team.digest_frequency
    team_local_now = _team_now(team)
    if freq == 'hourly':
        # Run at configured minute each hour
        if team.digest_minute is None:
            minute_ok = team_local_now.minute == 0
        else:
            minute_ok = team_local_now.minute == team.digest_minute
        if not minute_ok:
            return False
    elif freq == 'daily':
        hour_ok = team.digest_hour is not None and team_local_now.hour == team.digest_hour
        minute_ok = team.digest_minute is not None and team_local_now.minute == team.digest_minute
        if not (hour_ok and minute_ok):
            return False
    else:
        return False

    # Avoid duplicate runs within same minute
    if team.last_digest_at is None:
        return True
    delta = now_utc - team.last_digest_at
    if delta.total_seconds() < 60:
        return False
    # Also ensure frequency interval passed
    return delta >= _frequency_delta(freq)


def _digest_window(team: Team, now_utc: datetime) -> Tuple[datetime, datetime]:
    freq = team.digest_frequency
    if team.last_digest_at is not None:
        start = team.last_digest_at
    else:
        # first window: previous period
        start = now_utc - _frequency_delta(freq)
    end = now_utc
    return (start, end)


def build_digest_payload(team: Team, route: Route, events: List[Event]) -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    items = []
    for ev in events:
        sev = ev.severity or 'info'
        counts[sev] = counts.get(sev, 0) + 1
    # include up to 10 recent events
    for ev in events[:10]:
        items.append({
            'id': ev.id,
            'title': ev.title,
            'severity': ev.severity,
            'event_type': ev.event_type,
            'created_at': ev.created_at.isoformat() if ev.created_at else None,
        })
    return {
        'digest': True,
        'team_id': team.id,
        'team': team.name,
        'route_id': route.id,
        'channel': route.channel,
        'target': route.target,
        'counts': counts,
        'total_events': len(events),
        'sample_events': items,
    }


def run_digests_once() -> Dict[str, Any]:
    now_utc = _now_utc()
    results = {'checked': 0, 'ran': 0, 'deliveries': 0}
    teams = Team.query.filter_by(digest_enabled=True).all()
    for team in teams:
        results['checked'] += 1
        if not should_run_digest(team, now_utc):
            continue
        start, end = _digest_window(team, now_utc)
        # collect routes and events per route
        routes = Route.query.filter_by(team_id=team.id, active=True, mode='digest').all()
        deliveries_created = 0
        if routes:
            # get candidate events
            evs = Event.query.filter(
                Event.team_id == team.id,
                Event.created_at >= start,
                Event.created_at < end
            ).order_by(Event.created_at.desc()).all()
            for r in routes:
                matched = [ev for ev in evs if matches_filters(ev.to_dict(), r.filters or {})]
                if not matched:
                    continue
                payload = build_digest_payload(team, r, matched)
                queue_delivery(team_id=team.id, route_id=r.id, channel=r.channel, target=r.target, payload=payload, delivery_type='digest')
                deliveries_created += 1
        # update last_digest_at
        team.last_digest_at = now_utc
        db.session.add(team)
        db.session.commit()
        if deliveries_created > 0:
            results['deliveries'] += deliveries_created
            results['ran'] += 1
    return results

