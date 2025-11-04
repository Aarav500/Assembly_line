import os
import io
import json
import uuid
import tempfile
from datetime import datetime
from zipfile import ZipFile, ZIP_DEFLATED

from db import (
    insert_bundle, update_bundle,
    fetch_policies, fetch_controls, fetch_evidences, fetch_audit_logs, fetch_users
)
from utils import sha256_bytes, sha256_file, hmac_sha256, redact_email, pseudonym


README_TEXT = """
Audit & Compliance Export Bundle

This bundle contains read-only exports of governance artifacts for external audit.

Contents:
- manifest.json: bundle metadata, filters, and checksums of data files
- data/*.jsonl: line-delimited JSON files for each included entity
- checksums.txt: SHA256 checksums for each data file
- signature.json: Optional HMAC signature of manifest.json (if signing key configured)

Integrity:
Verify each data file against checksums.txt. The bundle ZIP SHA256 is provided out-of-band via API metadata.
""".strip()


def create_export_bundle(config, conn, filters, created_by):
    bundle_id = str(uuid.uuid4())
    insert_bundle(conn, bundle_id, created_by, status='creating', filters=filters)

    include = set(filters.get('include') or [])
    start = filters.get('start')
    end = filters.get('end')
    frameworks = filters.get('frameworks') or []
    anonymize = bool(filters.get('anonymize_pii'))

    tempdir = tempfile.mkdtemp(prefix=f"bundle_{bundle_id}_")
    data_dir = os.path.join(tempdir, 'data')
    os.makedirs(data_dir, exist_ok=True)

    file_registry = {}

    # Gather policies
    policies = []
    if 'policies' in include:
        policies = fetch_policies(conn, start=start, end=end, frameworks=frameworks)
        path = os.path.join(data_dir, 'policies.jsonl')
        write_jsonl(path, policies)
        file_registry['data/policies.jsonl'] = sha256_file(path)

    # Gather controls
    controls = []
    if 'controls' in include:
        policy_ids = [p['id'] for p in policies] if frameworks else None
        controls = fetch_controls(conn, start=start, end=end, policy_ids=policy_ids)
        path = os.path.join(data_dir, 'controls.jsonl')
        write_jsonl(path, controls)
        file_registry['data/controls.jsonl'] = sha256_file(path)

    # Gather evidences
    if 'evidences' in include:
        control_ids = [c['id'] for c in controls] if controls else None
        evidences = fetch_evidences(conn, start=start, end=end, control_ids=control_ids)
        path = os.path.join(data_dir, 'evidences.jsonl')
        write_jsonl(path, evidences)
        file_registry['data/evidences.jsonl'] = sha256_file(path)

    # Gather audit logs
    if 'audit_logs' in include:
        logs = fetch_audit_logs(conn, start=start, end=end)
        if anonymize:
            for l in logs:
                if l.get('actor'):
                    l['actor'] = pseudonym(l['actor'])
        path = os.path.join(data_dir, 'audit_logs.jsonl')
        write_jsonl(path, logs)
        file_registry['data/audit_logs.jsonl'] = sha256_file(path)

    # Gather users
    if 'users' in include:
        users = fetch_users(conn, start=start, end=end)
        if anonymize:
            for u in users:
                u['name'] = pseudonym(u.get('name', ''))
                if u.get('email'):
                    u['email'] = redact_email(u['email'])
        path = os.path.join(data_dir, 'users.jsonl')
        write_jsonl(path, users)
        file_registry['data/users.jsonl'] = sha256_file(path)

    # Manifest
    manifest = {
        'bundle_id': bundle_id,
        'created_at': datetime.utcnow().isoformat() + 'Z',
        'created_by': created_by,
        'label': filters.get('label'),
        'filters': filters,
        'app_version': config.get('APP_VERSION'),
        'files': [{'path': p, 'sha256': h} for p, h in sorted(file_registry.items())]
    }
    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode('utf-8')
    manifest_sha256 = sha256_bytes(manifest_bytes)

    # checksums.txt
    checksums_lines = [f"{h}  {p}" for p, h in sorted(file_registry.items())]
    checksums_txt = "\n".join(checksums_lines).encode('utf-8')

    # Optional signature
    signature_obj = None
    signing_key = config.get('SIGNING_KEY') or ''
    if signing_key:
        sig = hmac_sha256(signing_key.encode('utf-8'), manifest_bytes)
        signature_obj = {
            'algorithm': 'HMAC-SHA256',
            'target': 'manifest.json',
            'signature': sig,
            'manifest_sha256': manifest_sha256
        }

    # Build zip
    export_dir = config['EXPORT_DIR']
    os.makedirs(export_dir, exist_ok=True)
    zip_path = os.path.join(export_dir, f"{bundle_id}.zip")
    with ZipFile(zip_path, 'w', ZIP_DEFLATED) as zf:
        # write data files
        for rel_path in sorted(file_registry.keys()):
            abs_path = os.path.join(tempdir, rel_path)
            zf.write(abs_path, rel_path)
        zf.writestr('manifest.json', manifest_bytes)
        zf.writestr('checksums.txt', checksums_txt)
        zf.writestr('README.txt', README_TEXT)
        if signature_obj:
            zf.writestr('signature.json', json.dumps(signature_obj, indent=2).encode('utf-8'))

    zip_sha256 = sha256_file(zip_path)
    zip_size = os.path.getsize(zip_path)

    update_bundle(conn, bundle_id, status='ready', file_path=zip_path, sha256=zip_sha256, size_bytes=zip_size)

    # Return metadata for API
    return {
        'id': bundle_id,
        'created_at': manifest['created_at'],
        'created_by': created_by,
        'status': 'ready',
        'filters': filters,
        'file_path': zip_path,
        'sha256': zip_sha256,
        'size_bytes': zip_size,
        'download_url': f"/api/bundles/{bundle_id}/download"
    }


def write_jsonl(path, records):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False))
            f.write('\n')

