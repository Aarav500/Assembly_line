import json
import os
import platform
import socket
import hashlib
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List


def _now_iso():
    return datetime.utcnow().isoformat() + 'Z'


def _hash_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _hash_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def generate_evidence_package(evidence_dir: str,
                              event_id: str,
                              policy: Dict,
                              before_backups: List[Dict],
                              after_backups: List[Dict],
                              actions: List[Dict],
                              compliance_result: Dict,
                              note: str = None) -> Dict:
    base_dir = Path(evidence_dir) / event_id
    base_dir.mkdir(parents=True, exist_ok=True)

    created_at = _now_iso()

    system_info = {
        'hostname': socket.gethostname(),
        'platform': platform.platform(),
        'python_version': platform.python_version(),
        'arch': platform.machine(),
    }

    summary = {
        'event_id': event_id,
        'created_at': created_at,
        'note': note,
        'actions_count': len(actions),
        'before_count': len(before_backups),
        'after_count': len(after_backups),
        'compliant': compliance_result.get('compliant', False),
        'issues_count': len(compliance_result.get('issues', []))
    }

    # Hash inventory for after state
    after_hashes = [{'name': b['name'], 'hash_sha256': b.get('hash_sha256')} for b in after_backups]

    manifest = {
        'summary': summary,
        'policy_snapshot': policy,
        'system_info': system_info,
        'compliance_result': compliance_result,
        'before_backups': before_backups,
        'after_backups': after_backups,
        'after_hashes': after_hashes
    }

    manifest_json = json.dumps(manifest, sort_keys=True, indent=2).encode('utf-8')
    manifest_hash = _hash_bytes(manifest_json)

    # Write files
    manifest_path = base_dir / 'manifest.json'
    with open(manifest_path, 'wb') as f:
        f.write(manifest_json)

    actions_path = base_dir / 'actions.json'
    with open(actions_path, 'w', encoding='utf-8') as f:
        json.dump(actions, f, indent=2)

    readme_path = base_dir / 'README.txt'
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write('Backup retention compliance evidence package\n')
        f.write(f'Event ID: {event_id}\n')
        f.write(f'Created: {created_at}\n')
        f.write(f'Manifest SHA256: {manifest_hash}\n')
        f.write('Files included: manifest.json, actions.json, README.txt\n')

    # Zip it up
    zip_path = Path(evidence_dir) / f'{event_id}.zip'
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.write(manifest_path, arcname='manifest.json')
        z.write(actions_path, arcname='actions.json')
        z.write(readme_path, arcname='README.txt')

    return {
        'event_id': event_id,
        'created_at': created_at,
        'summary': summary,
        'manifest': manifest,
        'manifest_hash': manifest_hash,
        'zip_path': str(zip_path)
    }

