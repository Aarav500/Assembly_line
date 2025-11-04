import os
import json
import datetime as dt
from flask import current_app


def audit_event(action: str, user: str, path: str, outcome: str, extra: dict | None = None):
    cfg_enabled = getattr(current_app.config, 'AUDIT_ENABLED', True) if current_app else True
    if not cfg_enabled and os.getenv('AUDIT_ENABLED', '1') not in ('1', 'true', 'yes'):
        return
    record = {
        'ts': dt.datetime.utcnow().isoformat() + 'Z',
        'action': action,
        'user': user,
        'path': path,
        'outcome': outcome,
    }
    if extra:
        record.update(extra)
    print(json.dumps(record), flush=True)

