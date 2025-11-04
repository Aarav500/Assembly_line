import hashlib
import io
import json
import os
import uuid
import zipfile
from datetime import datetime
from typing import List, Dict
from werkzeug.utils import secure_filename

CHUNK_SIZE = 1024 * 1024


def compute_sha256(file_path: str) -> str:
    h = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b''):
            h.update(chunk)
    return h.hexdigest()


def save_upload(storage_dir: str, file_storage, subdir: str = 'evidence') -> Dict:
    os.makedirs(os.path.join(storage_dir, subdir), exist_ok=True)
    original_filename = file_storage.filename or 'evidence.bin'
    filename = secure_filename(original_filename) or 'evidence.bin'
    unique_prefix = uuid.uuid4().hex
    stored_filename = f"{unique_prefix}_{filename}"
    relative_path = os.path.join(subdir, stored_filename).replace('\\', '/')
    abs_path = os.path.join(storage_dir, relative_path)

    size_bytes = 0
    h = hashlib.sha256()
    with open(abs_path, 'wb') as out:
        stream = file_storage.stream
        while True:
            chunk = stream.read(CHUNK_SIZE)
            if not chunk:
                break
            out.write(chunk)
            size_bytes += len(chunk)
            h.update(chunk)

    sha256 = h.hexdigest()

    return {
        'original_filename': original_filename,
        'stored_filename': stored_filename,
        'relative_path': relative_path,
        'abs_path': abs_path,
        'size_bytes': size_bytes,
        'sha256': sha256,
    }


def build_bundle_manifest(bundle, evidences: List[Dict]) -> Dict:
    return {
        'bundle': {
            'id': bundle.id,
            'name': bundle.name,
            'description': bundle.description,
            'audit_id': bundle.audit_id,
            'created_at': bundle.created_at.isoformat() + 'Z',
            'bundle_hash': bundle.bundle_hash,
            'item_count': bundle.item_count,
        },
        'evidence': evidences,
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'schema_version': '1.0.0'
    }


def compute_bundle_hash(evidence_hashes: List[str]) -> str:
    # Deterministic hash: sort evidence hashes and hash their concatenation
    concat = ''.join(sorted(evidence_hashes)).encode('utf-8')
    return hashlib.sha256(concat).hexdigest()


def zip_bundle_in_memory(storage_dir: str, bundle, evidence_rows: List) -> io.BytesIO:
    # Prepare manifest entries
    evidence_entries = []
    checksums_lines = []

    for ev in evidence_rows:
        ev_rel_path = ev.relative_path.replace('\\', '/')
        entry = {
            'id': ev.id,
            'original_filename': ev.original_filename,
            'relative_path': ev_rel_path,
            'content_type': ev.content_type,
            'size_bytes': ev.size_bytes,
            'sha256': ev.sha256,
            'tags': ev.tags or [],
            'audit_id': ev.audit_id,
            'meta': ev.meta_json or {},
            'uploaded_at': ev.uploaded_at.isoformat() + 'Z',
        }
        evidence_entries.append(entry)
        checksums_lines.append(f"sha256 {ev_rel_path} {ev.sha256}")

    manifest = build_bundle_manifest(bundle, evidence_entries)

    mem_file = io.BytesIO()
    with zipfile.ZipFile(mem_file, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        # Add evidence files under evidence/ with their stored filenames
        for ev in evidence_rows:
            abs_path = os.path.join(storage_dir, ev.relative_path)
            arcname = ev.relative_path  # keep same relative path inside zip
            zf.write(abs_path, arcname)
        # Add manifest.json
        zf.writestr('manifest.json', json.dumps(manifest, indent=2, sort_keys=True))
        # Add checksums.txt
        zf.writestr('checksums.txt', '\n'.join(checksums_lines) + '\n')
    mem_file.seek(0)
    return mem_file

