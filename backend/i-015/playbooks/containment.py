from typing import Any, Dict, List, Optional

from config import Config
from models.incidents import add_action, update_action, update_incident_status
from services.isolation import get_isolation_provider
from services.key_revocation import get_key_revocation_provider
from utils.audit import log_audit


class ContainmentPlaybook:
    def __init__(self, incident_id: str, dry_run: Optional[bool] = None):
        self.incident_id = incident_id
        self.dry_run = Config.DEFAULT_DRY_RUN if dry_run is None else dry_run
        self.isolation_provider = get_isolation_provider(Config.ISOLATION_PROVIDER)
        self.key_provider = get_key_revocation_provider(Config.KEY_REVOCATION_PROVIDER)

    def run(self, assets: Optional[List[str]] = None, keys: Optional[List[Dict[str, Any]]] = None, reason: Optional[str] = None) -> Dict[str, Any]:
        assets = assets or []
        keys = keys or []

        action_id = add_action(self.incident_id, 'containment_playbook', 'running', {'dry_run': self.dry_run})
        log_audit(actor='containment-playbook', action='start', target=self.incident_id, status='running', detail=f'Assets: {len(assets)}, Keys: {len(keys)}, dry_run: {self.dry_run}')

        results = {
            'assets': [],
            'keys': [],
            'dry_run': self.dry_run,
        }
        errors = []

        try:
            # Isolate assets
            for asset in assets:
                try:
                    if self.dry_run:
                        res = {'asset_id': asset, 'provider': self.isolation_provider.name, 'status': 'dry_run', 'details': 'No action taken'}
                    else:
                        res = self.isolation_provider.isolate(asset_id=asset, reason=reason, incident_id=self.incident_id)
                    results['assets'].append(res)
                except Exception as e:
                    err = f'asset:{asset} error:{str(e)}'
                    errors.append(err)
                    results['assets'].append({'asset_id': asset, 'status': 'error', 'error': str(e)})

            # Revoke keys
            for item in keys:
                key_id = item.get('key_id') if isinstance(item, dict) else str(item)
                user = item.get('user') if isinstance(item, dict) else None
                try:
                    if self.dry_run:
                        res = {'key_id': key_id, 'user': user, 'provider': self.key_provider.name, 'status': 'dry_run', 'details': 'No action taken'}
                    else:
                        res = self.key_provider.revoke_key(key_id=key_id, user=user, reason=reason, incident_id=self.incident_id)
                    results['keys'].append(res)
                except Exception as e:
                    err = f'key:{key_id} error:{str(e)}'
                    errors.append(err)
                    results['keys'].append({'key_id': key_id, 'user': user, 'status': 'error', 'error': str(e)})

            summary = {
                'isolated_assets': len([a for a in results['assets'] if a.get('status') in ('isolated', 'dry_run')]),
                'revoked_keys': len([k for k in results['keys'] if k.get('status') in ('revoked', 'dry_run')]),
                'errors': len(errors),
            }
            results['summary'] = summary

            status = 'completed' if not errors else 'partial'
            update_action(action_id, status=status, result=results)
            log_audit(actor='containment-playbook', action='complete', target=self.incident_id, status=status, detail=str(summary))

            # Update incident status
            update_incident_status(self.incident_id, 'contained' if status == 'completed' else 'partial_contained')

            return results
        except Exception as e:
            update_action(action_id, status='failed', result={'error': str(e), 'partial': results})
            log_audit(actor='containment-playbook', action='failed', target=self.incident_id, status='failed', detail=str(e))
            update_incident_status(self.incident_id, 'containment_failed')
            raise

