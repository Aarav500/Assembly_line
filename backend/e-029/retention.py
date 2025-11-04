from datetime import datetime, timedelta
from typing import List, Dict


def _parse_iso(dt_str: str) -> datetime:
    # trims trailing Z if present
    if dt_str.endswith('Z'):
        dt_str = dt_str[:-1]
    # attempt to parse fractional seconds if present
    try:
        return datetime.fromisoformat(dt_str)
    except Exception:
        # fallback
        return datetime.strptime(dt_str, '%Y-%m-%dT%H:%M:%S')


def _now():
    return datetime.utcnow()


def check_compliance(policy: Dict, backups: List[Dict]) -> Dict:
    now = _now()
    retain_days = int(policy.get('retain_days', 30))
    min_backups = int(policy.get('min_backups', 7))
    max_backups = policy.get('max_backups')
    max_backups = int(max_backups) if max_backups is not None else None
    freq_hours = int(policy.get('require_frequency_hours', 24))

    issues = []
    metrics = {}

    # Parse times
    times = [_parse_iso(b['created_at']) for b in backups]

    metrics['total_backups'] = len(backups)

    # Check minimum count
    if len(backups) < min_backups:
        issues.append(f"Only {len(backups)} backups present; minimum required is {min_backups}")

    # Check frequency gaps
    if freq_hours > 0 and len(times) >= 2:
        max_gap = timedelta(0)
        gaps = []
        for prev, curr in zip(times, times[1:]):
            gap = curr - prev
            gaps.append(gap.total_seconds())
            if gap > max_gap:
                max_gap = gap
        metrics['max_gap_hours'] = round(max_gap.total_seconds() / 3600, 3)
        if max_gap > timedelta(hours=freq_hours * 1.5):
            issues.append(f"Detected gap of {metrics['max_gap_hours']} hours exceeding 1.5x required frequency {freq_hours}h")
    elif freq_hours > 0 and len(times) == 1:
        since_last = now - times[-1]
        metrics['since_last_hours'] = round(since_last.total_seconds() / 3600, 3)
        if since_last > timedelta(hours=freq_hours * 1.5):
            issues.append(f"Only one backup found and it is {metrics['since_last_hours']} hours old; frequency is {freq_hours}h")

    # Determine deletion candidates
    cutoff = now - timedelta(days=retain_days)

    # Use indexes to ensure stable selection
    indexed = [
        {
            'idx': i,
            'name': b['name'],
            'path': b['path'],
            'created_at': b['created_at'],
            'created_dt': times[i],
            'size': b['size'],
            'hash_sha256': b.get('hash_sha256')
        }
        for i, b in enumerate(backups)
    ]

    # Sort oldest first
    indexed.sort(key=lambda x: x['created_dt'])

    # Initial keep set: keep all newer than cutoff and ensure at least min_backups newest
    keep = set()
    # Keep all newer than cutoff
    for item in indexed:
        if item['created_dt'] >= cutoff:
            keep.add(item['idx'])

    # Ensure at least min_backups newest kept
    newest = indexed[-min_backups:] if min_backups > 0 else []
    for item in newest:
        keep.add(item['idx'])

    # Apply max_backups by marking oldest beyond limit as deletable (but never below min_backups)
    total = len(indexed)
    deletion_candidates = []
    if max_backups is not None and total > max_backups:
        over = total - max_backups
        # Oldest items to consider for deletion, skipping those forcibly kept
        for item in indexed:
            if over <= 0:
                break
            if item['idx'] in keep:
                continue
            deletion_candidates.append(_candidate_dict(item, reason=f"exceeds max_backups {max_backups}"))
            keep.add(item['idx'])  # mark as accounted
            over -= 1

    # Delete items older than cutoff that are not in keep set
    for item in indexed:
        if item['idx'] in keep:
            continue
        if item['created_dt'] < cutoff:
            deletion_candidates.append(_candidate_dict(item, reason=f"older than retain_days {retain_days}"))

    # Compute after count projection
    projected_after = total - len(deletion_candidates)
    if projected_after < min_backups:
        # Do not propose deletions that would violate min_backups
        # Trim the candidates list accordingly (keep newest among candidates)
        to_retain = min_backups - projected_after
        if to_retain > 0 and len(deletion_candidates) > 0:
            # Keep the newest among deletion candidates to respect min_backups
            deletion_candidates.sort(key=lambda x: _parse_iso(x['created_at']))
            deletion_candidates = deletion_candidates[:max(0, len(deletion_candidates) - to_retain)]

    compliant = len(issues) == 0

    return {
        'compliant': compliant,
        'issues': issues,
        'metrics': metrics,
        'deletion_candidates': deletion_candidates,
        'policy_cutoff_utc': cutoff.isoformat() + 'Z',
        'evaluated_at': _now().isoformat() + 'Z'
    }


def _candidate_dict(item, reason: str):
    return {
        'name': item['name'],
        'path': item['path'],
        'created_at': item['created_dt'].isoformat() + 'Z',
        'size': item['size'],
        'hash_sha256': item.get('hash_sha256'),
        'reason': reason
    }

