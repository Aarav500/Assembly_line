from typing import Dict, Any, Optional
from utils.audit import log_audit


class BaseKeyRevocationProvider:
    name = 'base'

    def revoke_key(self, key_id: str, user: Optional[str] = None, reason: Optional[str] = None, incident_id: Optional[str] = None) -> Dict[str, Any]:
        raise NotImplementedError


class DummyKeyRevocationProvider(BaseKeyRevocationProvider):
    name = 'dummy'

    def revoke_key(self, key_id: str, user: Optional[str] = None, reason: Optional[str] = None, incident_id: Optional[str] = None) -> Dict[str, Any]:
        target = f'key:{key_id}' + (f' user:{user}' if user else '')
        detail = f'Dummy key revocation for {target}. Reason: {reason or "n/a"}. Incident: {incident_id or "n/a"}'
        log_audit(actor='containment-playbook', action='revoke_key', target=target, status='success', detail=detail)
        return {
            'key_id': key_id,
            'user': user,
            'provider': self.name,
            'status': 'revoked',
            'details': detail,
        }


def get_key_revocation_provider(name: str) -> BaseKeyRevocationProvider:
    # Extend here for real providers
    if name.lower() == 'dummy':
        return DummyKeyRevocationProvider()
    return DummyKeyRevocationProvider()

