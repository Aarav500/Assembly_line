import logging
import re
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple

from flask import current_app, request, jsonify, make_response

from utils import compat

logger = logging.getLogger(__name__)


Version = str


def parse_version(v: str) -> Tuple[int, int]:
    try:
        parts = v.strip().split('.')
        if len(parts) == 1:
            return int(parts[0]), 0
        return int(parts[0]), int(parts[1])
    except Exception:
        return (0, 0)


def normalize_version(v: Optional[str], supported: List[str]) -> Optional[str]:
    if v is None:
        return None
    v = v.strip().lower().replace('v', '')
    # Accept formats like '2', '2.0', '2.1'
    if '.' not in v:
        candidate = f"{v}.0"
        if candidate in supported:
            return candidate
        return candidate
    return v


def sort_versions_desc(versions: List[str]) -> List[str]:
    return sorted(versions, key=lambda x: parse_version(x), reverse=True)


def choose_served_version(requested: Version, available: List[Version]) -> Tuple[Version, str]:
    # Returns (served, mode) where mode in {'exact','downcast','upcast'}
    # exact: exact match
    # downcast: serve a newer version than requested, adapt down
    # upcast: serve an older version than requested, adapt up (best-effort)
    if requested in available:
        return requested, 'exact'

    req_tuple = parse_version(requested)
    sorted_av = sort_versions_desc(available)

    lower_or_equal = [v for v in sorted_av if parse_version(v) <= req_tuple]
    higher = [v for v in sorted_av if parse_version(v) > req_tuple]

    if higher:
        # Serve the smallest higher (closest newer) for downcast
        served = higher[-1]
        return served, 'downcast'

    if lower_or_equal:
        # Serve the highest lower/equal (closest older) for upcast
        served = lower_or_equal[0]
        return served, 'upcast'

    # Fallback to latest
    return current_app.config['LATEST_VERSION'], 'exact'


def detect_version(req, path_version: Optional[str] = None) -> Version:
    cfg = current_app.config
    supported = cfg['SUPPORTED_VERSIONS']

    # 1. Path version e.g., /api/v2/items or /api/v2.0/items
    if path_version:
        pv = normalize_version(path_version, supported)
        if pv:
            return pv

    # 2. Query parameter ?api-version=2 or 2.0
    qv = req.args.get('api-version')
    if qv:
        nv = normalize_version(qv, supported)
        if nv:
            return nv

    # 3. Header X-API-Version
    hv = req.headers.get('X-API-Version')
    if hv:
        nv = normalize_version(hv, supported)
        if nv:
            return nv

    # 4. Accept header, look for version parameter
    accept = req.headers.get('Accept', '')
    if 'version=' in accept:
        # Parse version parameter from media range(s)
        for part in accept.split(','):
            if 'version=' in part:
                m = re.search(r'version\s*=\s*([\dv\.]+)', part)
                if m:
                    nv = normalize_version(m.group(1), supported)
                    if nv:
                        return nv

    # Default to latest
    return cfg['LATEST_VERSION']


def is_deprecated(version: Version) -> bool:
    return version in current_app.config.get('DEPRECATED_VERSIONS', {})


def apply_deprecation_headers(resp, requested: Version, served: Version):
    cfg = current_app.config
    deprecated_meta = cfg.get('DEPRECATED_VERSIONS', {}).get(requested) or cfg.get('DEPRECATED_VERSIONS', {}).get(served)
    if not deprecated_meta:
        return

    resp.headers['Deprecation'] = 'true'
    sunset = deprecated_meta.get('sunset')
    if sunset:
        resp.headers['Sunset'] = str(sunset)
    link = deprecated_meta.get('link')
    if link:
        resp.headers['Link'] = f"<{link}>; rel=deprecation"
    notice = deprecated_meta.get('notice') or 'This API version is deprecated.'
    if cfg.get('INCLUDE_WARNING_HEADERS', True):
        resp.headers['Warning'] = f"299 - \"{notice}\""

    if cfg.get('LOG_VERSION_EVENTS', True):
        logger.warning('Deprecated version in use. requested=%s served=%s sunset=%s', requested, served, sunset)


def apply_negotiation_headers(resp, requested: Version, served: Version, mode: str):
    cfg = current_app.config
    resp.headers['API-Requested-Version'] = requested
    resp.headers['API-Served-Version'] = served
    resp.headers['API-Latest-Version'] = cfg['LATEST_VERSION']
    resp.headers['API-Supported-Versions'] = ','.join(cfg['SUPPORTED_VERSIONS'])

    if mode == 'downcast' and cfg.get('INCLUDE_WARNING_HEADERS', True):
        resp.headers['Warning'] = resp.headers.get('Warning', '') or ''
        message = f"Served newer version {served} adapted to requested {requested}."
        resp.headers['Warning'] = (resp.headers['Warning'] + (', ' if resp.headers['Warning'] else '') + f"299 - \"{message}\"")
    elif mode == 'upcast' and cfg.get('INCLUDE_WARNING_HEADERS', True):
        message = f"Requested {requested} not available; served older {served}. Some fields may be missing."
        resp.headers['Warning'] = (resp.headers.get('Warning', '') + (', ' if resp.headers.get('Warning') else '') + f"299 - \"{message}\"")


class VersionRouter:
    def __init__(self):
        # endpoint -> version -> handler
        self.registry: Dict[str, Dict[Version, Callable]] = {}

    def register(self, endpoint: str, version: Version, handler: Callable):
        self.registry.setdefault(endpoint, {})[version] = handler

    def available_versions(self, endpoint: str) -> List[Version]:
        return list(self.registry.get(endpoint, {}).keys())

    def dispatch(self, endpoint: str, req, method: str, path_version: Optional[str] = None, resource_name: Optional[str] = None):
        cfg = current_app.config
        requested = detect_version(req, path_version)
        available = self.available_versions(endpoint)

        if not available:
            return make_response(jsonify({
                'error': 'Endpoint not implemented',
                'endpoint': endpoint
            }), 501)

        served, mode = choose_served_version(requested, available)
        handler = self.registry[endpoint].get(served)

        # Prepare request payload adaptation if needed
        payload = None
        if req.is_json:
            try:
                payload = req.get_json(silent=True) or None
            except Exception:
                payload = None

        adapted_in = payload
        if payload is not None and (served != requested):
            adapted_in = compat.adapt_request(resource_name or endpoint, method, from_version=requested, to_version=served, data=payload)

        # Call handler with adapted payload when appropriate
        result = None
        if adapted_in is not None and method in ('POST', 'PUT', 'PATCH'):
            result = handler(adapted_in)
        else:
            result = handler()

        # Normalize result into (body, status)
        if isinstance(result, tuple) and len(result) == 2:
            body, status = result
        else:
            body, status = result, 200

        # Adapt response if versions differ
        if served != requested:
            body = compat.adapt_response(resource_name or endpoint, method, from_version=served, to_version=requested, data=body)

        resp = make_response(jsonify(body), status)

        # Apply negotiation & deprecation headers
        apply_negotiation_headers(resp, requested, served, mode)
        apply_deprecation_headers(resp, requested, served)

        if cfg.get('LOG_VERSION_EVENTS', True):
            logger.info('Version negotiation endpoint=%s requested=%s served=%s mode=%s', endpoint, requested, served, mode)

        return resp


router = VersionRouter()

