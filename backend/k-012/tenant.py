from dataclasses import dataclass
from typing import Any, Optional
from flask import g
from models import Organization
from cache import tenant_cache


@dataclass
class TenantContext:
    org: Organization

    def cache_get(self, key: str) -> Optional[Any]:
        return tenant_cache.get(self.org.id, key)

    def cache_set(self, key: str, value: Any, ttl_seconds: Optional[int] = None):
        tenant_cache.set(self.org.id, key, value, ttl_seconds)

    def cache_delete(self, key: str):
        tenant_cache.delete(self.org.id, key)


def current_tenant() -> TenantContext:
    if not hasattr(g, 'org') or g.org is None:
        raise RuntimeError('Tenant context requested outside of authenticated request')
    if not hasattr(g, 'tenant'):
        g.tenant = TenantContext(org=g.org)
    return g.tenant


