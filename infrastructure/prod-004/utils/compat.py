from copy import deepcopy
from typing import Any, List


def _ensure_list(data):
    if isinstance(data, list):
        return data
    return [data]


def adapt_request(resource: str, method: str, from_version: str, to_version: str, data: Any):
    # Copy to avoid mutating original
    d = deepcopy(data)

    # Example adapters for 'items' resource
    if resource in ('items_list', 'items_create', 'items'):
        # Normalize resource name variants
        if method == 'POST':
            if from_version.startswith('1') and to_version.startswith('2'):
                # v1 -> v2: rename 'title' to 'name', default price=0
                if isinstance(d, dict):
                    if 'title' in d and 'name' not in d:
                        d['name'] = d.pop('title')
                    d.setdefault('price', 0.0)
            elif from_version.startswith('2') and to_version.startswith('1'):
                # v2 -> v1: rename 'name' to 'title', drop price
                if isinstance(d, dict):
                    if 'name' in d and 'title' not in d:
                        d['title'] = d['name']
                    d.pop('price', None)
        # No request body for GET list

    return d


def adapt_response(resource: str, method: str, from_version: str, to_version: str, data: Any):
    d = deepcopy(data)

    def v2_to_v1_item(item: dict) -> dict:
        out = {k: v for k, v in item.items() if k in ('id', 'name')}
        # rename name -> title
        if 'name' in out:
            out['title'] = out.pop('name')
        return out

    def v1_to_v2_item(item: dict) -> dict:
        out = {k: v for k, v in item.items()}
        # rename title -> name
        if 'title' in out and 'name' not in out:
            out['name'] = out.pop('title')
        out.setdefault('price', 0.0)
        out.setdefault('created_at', None)
        return out

    if resource in ('items_list', 'items_create', 'items'):
        if method == 'GET':
            # Lists
            if from_version.startswith('2') and to_version.startswith('1'):
                items = _ensure_list(d)
                return [v2_to_v1_item(x) for x in items]
            if from_version.startswith('1') and to_version.startswith('2'):
                items = _ensure_list(d)
                return [v1_to_v2_item(x) for x in items]
        elif method == 'POST':
            # Single item created
            if isinstance(d, dict):
                if from_version.startswith('2') and to_version.startswith('1'):
                    return v2_to_v1_item(d)
                if from_version.startswith('1') and to_version.startswith('2'):
                    return v1_to_v2_item(d)

    return d

