from typing import Dict, Any, Optional
from utils.audit import log_audit


class BaseIsolationProvider:
    name = 'base'

    def isolate(self, asset_id: str, reason: Optional[str] = None, incident_id: Optional[str] = None) -> Dict[str, Any]:
        raise NotImplementedError


class DummyIsolationProvider(BaseIsolationProvider):
    name = 'dummy'

    def isolate(self, asset_id: str, reason: Optional[str] = None, incident_id: Optional[str] = None) -> Dict[str, Any]:
        detail = f'Dummy isolate invoked for {asset_id}. Reason: {reason or "n/a"}. Incident: {incident_id or "n/a"}'
        log_audit(actor='containment-playbook', action='isolate', target=asset_id, status='success', detail=detail)
        return {
            'asset_id': asset_id,
            'provider': self.name,
            'status': 'isolated',
            'details': detail,
        }


def get_isolation_provider(name: str) -> BaseIsolationProvider:
    # Extend here to support real providers
    if name.lower() == 'dummy':
        return DummyIsolationProvider()
    # Unknown provider -> fallback to dummy with note
    return DummyIsolationProvider()

