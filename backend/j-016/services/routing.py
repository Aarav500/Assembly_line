from typing import Dict, Any, List


def matches_filters(event: Dict[str, Any], filters: Dict[str, Any]) -> bool:
    if not filters:
        return True
    # Expected event keys: severity, event_type, tags(list)
    sev = event.get('severity')
    ev_type = event.get('event_type')
    tags = set(event.get('tags') or [])

    severities = set(filters.get('severities') or [])
    if severities and sev not in severities:
        return False

    event_types = set(filters.get('event_types') or [])
    if event_types and ev_type not in event_types:
        return False

    include_tags: List[str] = filters.get('include_tags') or []
    if include_tags:
        if tags.isdisjoint(include_tags):
            return False

    exclude_tags: List[str] = filters.get('exclude_tags') or []
    if not tags.isdisjoint(exclude_tags):
        return False

    return True

