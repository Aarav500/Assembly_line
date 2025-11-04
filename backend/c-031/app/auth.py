from __future__ import annotations
from typing import Set
from flask import request


def get_roles_from_request() -> Set[str]:
    """Extract user roles from headers.
    Simulates authentication by using X-Roles (comma-separated) or X-Role.
    Roles are normalized to lowercase.
    """
    hdr = request.headers.get("X-Roles") or request.headers.get("X-Role")
    if not hdr:
        return set()
    return {part.strip().lower() for part in hdr.split(",") if part.strip()}

