from __future__ import annotations
from flask import current_app, request, g
from typing import Optional


def _version_from_path(path: str) -> Optional[str]:
    # Expecting /api/v1/... or /api/v2/...
    parts = [p for p in path.split('/') if p]
    try:
        api_idx = parts.index('api')
    except ValueError:
        return None
    if api_idx + 1 < len(parts):
        candidate = parts[api_idx + 1]
        if candidate in current_app.config['SUPPORTED_VERSIONS']:
            return candidate
    return None


def _version_from_query() -> Optional[str]:
    v = request.args.get('version') or request.args.get('v')
    if not v:
        return None
    v = str(v).lower().strip()
    if v.startswith('v'):
        return v
    # allow raw nums like 1 -> v1
    if v.isdigit():
        return f"v{v}"
    return None


def _version_from_header() -> Optional[str]:
    # X-API-Version: 1 or v1
    hv = request.headers.get('X-API-Version')
    if hv:
        hv = hv.lower().strip()
        if hv.startswith('v'):
            return hv
        if hv.isdigit():
            return f"v{hv}"
    # Accept: application/vnd.<vendor>+json; version=2
    accept = request.headers.get('Accept', '')
    if 'version=' in accept:
        try:
            for part in accept.split(';'):
                if 'version=' in part:
                    ver = part.split('=')[1].strip()
                    if ver.startswith('v'):
                        return ver
                    if ver.isdigit():
                        return f"v{ver}"
        except Exception:
            pass
    # Accept: application/vnd.<vendor>.v2+json
    if 'application/vnd.' in accept and '+json' in accept:
        try:
            media = accept.split(',')[0].split(';')[0]
            vendor_part = media.split('application/vnd.')[-1].split('+json')[0]
            if '.v' in vendor_part:
                maybe_v = vendor_part.split('.v')[-1]
                if maybe_v.isdigit():
                    return f"v{maybe_v}"
        except Exception:
            pass
    return None


def resolve_version() -> str:
    # Priority: explicit path > header > query > default
    path_version = _version_from_path(request.path)
    if path_version:
        g.explicit_path_version = True
        return path_version
    g.explicit_path_version = False

    header_version = _version_from_header()
    if header_version in current_app.config['SUPPORTED_VERSIONS']:
        return header_version

    query_version = _version_from_query()
    if query_version in current_app.config['SUPPORTED_VERSIONS']:
        return query_version

    return current_app.config['DEFAULT_API_VERSION']


def versioning_before_request():
    g.api_version = resolve_version()


def versioning_after_request(response):
    # Add version headers and deprecation metadata
    version = getattr(g, 'api_version', current_app.config['DEFAULT_API_VERSION'])
    response.headers['X-API-Version'] = version

    deprecations = current_app.config.get('DEPRECATIONS', {})
    if version in deprecations:
        meta = deprecations[version]
        response.headers['Deprecation'] = 'true'
        if meta.get('sunset'):
            response.headers['Sunset'] = meta['sunset']
        if meta.get('link'):
            response.headers.add('Link', f"<{meta['link']}>; rel=deprecation")
        # Add Warning 299 per RFC7234 (non-critical warnings)
        note = meta.get('note', 'Deprecated API version')
        response.headers['Warning'] = f"299 - \"{note}\""

    # Content negotiation hint when implicit negotiation was used
    if not getattr(g, 'explicit_path_version', False):
        response.headers['Vary'] = ', '.join(sorted(set(filter(None, [
            response.headers.get('Vary'), 'Accept', 'X-API-Version'
        ]))))

    return response

