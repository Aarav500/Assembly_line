from functools import wraps
from typing import Optional
from flask import request, g, jsonify
from models import db, Organization


def _extract_bearer_token() -> Optional[str]:
    auth = request.headers.get('Authorization', '')
    parts = auth.split()
    if len(parts) == 2 and parts[0].lower() == 'bearer':
        return parts[1]
    return None


def load_org_from_api_key() -> Optional[Organization]:
    token = _extract_bearer_token()
    if not token:
        return None
    return db.session.execute(db.select(Organization).filter_by(api_key=token)).scalar_one_or_none()


def org_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        org = load_org_from_api_key()
        if not org:
            return jsonify({"error": {"code": "unauthorized", "message": "Invalid or missing API key"}}), 401
        # Optional header consistency check to prevent confused deputy
        header_org = request.headers.get('X-Org-ID')
        if header_org is not None and str(org.id) != header_org:
            return jsonify({"error": {"code": "org_mismatch", "message": "X-Org-ID does not match API key"}}), 403
        g.org = org
        return fn(*args, **kwargs)
    return wrapper


