import os
import uuid
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

try:
    import requests
except Exception:
    requests = None


class IdeaterClient:
    def __init__(self, base_url: Optional[str], import_endpoint: Optional[str], token: Optional[str], workspace_id: Optional[str], workspace_url: Optional[str] = None):
        self.base_url = base_url.rstrip('/') if base_url else None
        self.import_endpoint = import_endpoint.rstrip('/') if import_endpoint else None
        self.token = token
        self.workspace_id = workspace_id
        self.workspace_url = workspace_url.rstrip('/') if workspace_url else None

    def _headers(self) -> Dict[str, str]:
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        return headers

    def import_features(self, features: List[Dict[str, Any]], source: Dict[str, Any]) -> Dict[str, Any]:
        # Prepare summary
        idea_count = sum(1 for f in features if f.get('kind') == 'idea')
        component_count = sum(1 for f in features if f.get('kind') == 'component')

        payload = {
            'workspace_id': self.workspace_id,
            'source': {
                'name': source.get('name') or 'Imported Project',
                'url': source.get('url'),
            },
            'features': features,
        }

        # Try direct import endpoint if configured
        if self.import_endpoint and requests:
            try:
                resp = requests.post(self.import_endpoint, headers=self._headers(), data=json.dumps(payload), timeout=30)
                resp.raise_for_status()
                data = resp.json() if 'application/json' in resp.headers.get('Content-Type', '') else {'status': 'ok'}
                import_id = data.get('import_id') or str(uuid.uuid4())
                open_url = data.get('open_url') or (f"{self.workspace_url}/imports/{import_id}" if self.workspace_url else None)
                return {
                    'import_id': import_id,
                    'status': 'ok',
                    'summary': {
                        'ideas': idea_count,
                        'components': component_count,
                        'total': len(features)
                    },
                    'open_url': open_url,
                    'items': data.get('items') or features,
                    'workspace_id': self.workspace_id,
                }
            except Exception as e:
                # Fall through to simulate
                pass

        # Fallback simulation: store to local file
        import_id = str(uuid.uuid4())
        record = {
            'import_id': import_id,
            'workspace_id': self.workspace_id,
            'source': payload['source'],
            'created_at': datetime.utcnow().isoformat() + 'Z',
            'summary': {
                'ideas': idea_count,
                'components': component_count,
                'total': len(features)
            },
            'items': features,
            'open_url': f"{self.workspace_url}/imports/{import_id}" if self.workspace_url else None,
        }
        try:
            os.makedirs('data/imports', exist_ok=True)
            with open(f'data/imports/{import_id}.json', 'w', encoding='utf-8') as f:
                json.dump(record, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return record

