from __future__ import annotations
import re
from typing import Any, Dict, List, Optional, Set
from flask import current_app, request, jsonify
from .auth import get_roles_from_request
from . import config as rbac_config


def require_roles(*roles: str):
    """Decorator to require at least one of the given roles for the endpoint.
    Explicit decorators override automatic pattern-based RBAC.
    """
    required = {r.lower() for r in roles}

    def decorator(func):
        setattr(func, "_required_roles", required)
        return func

    return decorator


def sensitive(level: str = "medium"):
    """Decorator to mark an endpoint as sensitive by semantic level.
    The actual roles are resolved at request-time using configured levels.
    """

    def decorator(func):
        setattr(func, "_sensitive_level", level)
        return func

    return decorator


def _compile_patterns(patterns: List[Dict[str, Any]]):
    compiled = []
    for item in patterns:
        pat = item.get("pattern")
        roles = set(map(str.lower, item.get("roles", set())))
        if not pat or not roles:
            continue
        compiled.append({"re": re.compile(pat), "roles": roles})
    return compiled


def _resolve_required_roles() -> Optional[Set[str]]:
    """Determine required roles for current request, if any.
    Order of precedence:
    1) @require_roles decorator on the view
    2) @sensitive(level) decorator mapped via configured levels
    3) Automatic pattern matches (first match wins)
    If none apply, return None (public endpoint).
    """
    view_name = request.endpoint
    if not view_name:
        return None

    view = current_app.view_functions.get(view_name)
    if not view:
        return None

    # Explicit decorator wins
    explicit = getattr(view, "_required_roles", None)
    if explicit:
        return set(map(str.lower, explicit))

    # Level-based sensitive decorator
    level = getattr(view, "_sensitive_level", None)
    if level:
        levels = current_app.config.get("RBAC_SENSITIVE_LEVELS", {})
        roles = levels.get(level, set())
        if roles:
            return set(map(str.lower, roles))

    # Automatic pattern matching
    for item in current_app.config.get("RBAC_COMPILED_PATTERNS", []):
        if item["re"].search(request.path):
            return item["roles"]

    return None


def _forbidden_response():
    return jsonify({"error": "forbidden", "reason": "RBAC: insufficient role"}), 403


def init_app(app):
    # Load and compile patterns
    patterns = getattr(app.config, "RBAC_SENSITIVE_PATTERNS", None) or rbac_config.SENSITIVE_PATTERNS
    levels = getattr(app.config, "RBAC_SENSITIVE_LEVELS", None) or rbac_config.SENSITIVE_LEVELS

    app.config["RBAC_COMPILED_PATTERNS"] = _compile_patterns(patterns)
    app.config["RBAC_SENSITIVE_LEVELS"] = {k: {r.lower() for r in v} for k, v in levels.items()}

    @app.before_request
    def _rbac_enforce():
        required = _resolve_required_roles()
        if not required:
            return None  # public

        roles = get_roles_from_request()
        if not roles:
            return _forbidden_response()

        if roles.isdisjoint(required):
            return _forbidden_response()

        return None


__all__ = ["require_roles", "sensitive", "init_app"]

