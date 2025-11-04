import contextvars
from urllib.parse import urlparse

from flask import request

from extensions import db
from models import Tenant

_current_tenant = contextvars.ContextVar('current_tenant', default=None)


def set_current_tenant(tenant: Tenant | None):
    _current_tenant.set(tenant)


def get_current_tenant() -> Tenant | None:
    return _current_tenant.get()


def resolve_tenant_from_request():
    # Priority: X-API-Key -> X-Tenant-Id -> subdomain slug
    api_key = request.headers.get('X-API-Key')
    if api_key:
        t = Tenant.query.filter_by(api_key=api_key).first()
        if t:
            return t
    tenant_id = request.headers.get('X-Tenant-Id')
    if tenant_id:
        t = Tenant.query.filter_by(id=tenant_id).first()
        if t:
            return t
    # Subdomain: slug.domain.tld
    host = request.host.split(':')[0]
    parts = host.split('.')
    if len(parts) >= 3:
        slug = parts[0]
        t = Tenant.query.filter_by(slug=slug).first()
        if t:
            return t
    return None


def tenancy_before_request():
    tenant = resolve_tenant_from_request()
    set_current_tenant(tenant)


def tenancy_teardown_request(exception=None):
    set_current_tenant(None)

