import json
import os
import platform
import shutil
import sys
import tempfile
import time
from typing import Dict, Tuple
from flask import current_app
from models import Run, RunDataset, Artifact
from utils.checksum import sha256_of_file
from utils.storage import ensure_dir


def build_manifest(run: Run) -> Dict:
    datasets = []
    for rd in run.datasets:
        datasets.append({
            'role': rd.role,
            'dataset': rd.dataset.to_dict(),
            'snapshot_path': rd.snapshot_path,
        })

    artifacts = []
    for a in run.artifacts:
        artifacts.append({
            'id': a.id,
            'type': a.type,
            'path': a.path,
            'checksum': a.checksum,
            'size_bytes': a.size_bytes,
            'mime_type': a.mime_type,
            'description': a.description,
        })

    manifest = {
        'manifest_version': 1,
        'generated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'run': {
            'id': run.id,
            'name': run.name,
            'status': run.status,
            'started_at': run.started_at.isoformat() if run.started_at else None,
            'ended_at': run.ended_at.isoformat() if run.ended_at else None,
            'random_seed': run.random_seed,
            'parameters': run.parameters,
            'metrics': run.metrics,
            'notes': run.notes,
        },
        'code_version': run.code_version.to_dict() if run.code_version else None,
        'environment': run.environment.to_dict() if run.environment else None,
        'datasets': datasets,
        'artifacts': artifacts,
        'reproduction': {
            'steps': [
                '1. Create an isolated environment (e.g., Docker, venv, or Conda).',
                '2. Install dependencies from environment/pip_freeze.txt (or conda.yml if provided).',
                '3. Checkout the repo to the specified commit (code/commit.txt) and apply patch if present.',
                '4. Verify dataset checksums. If snapshots included, place them at expected paths.',
                '5. Set random seed from manifest.',
                '6. Run training script with parameters from manifest.',
            ]
        }
    }
    return manifest


def create_bundle_for_run(run: Run) -> Tuple[str, str, int]:
    storage_dir = current_app.config['STORAGE_DIR']
    bundles_dir = os.path.join(storage_dir, 'bundles')
    ensure_dir(bundles_dir)

    tmpdir = tempfile.mkdtemp(prefix=f'bundle-run-{run.id}-')
    try:
        # Directory structure
        env_dir = os.path.join(tmpdir, 'environment')
        code_dir = os.path.join(tmpdir, 'code')
        ds_dir = os.path.join(tmpdir, 'datasets')
        arts_dir = os.path.join(tmpdir, 'artifacts')
        for d in (env_dir, code_dir, ds_dir, arts_dir):
            ensure_dir(d)

        # Environment files
        if run.environment:
            if run.environment.pip_freeze:
                with open(os.path.join(env_dir, 'pip_freeze.txt'), 'w', encoding='utf-8') as f:
                    f.write(run.environment.pip_freeze)
            os_info = run.environment.os_info or {}
        else:
            os_info = {
                'platform': platform.platform(),
                'python_version': sys.version,
            }
        with open(os.path.join(env_dir, 'os_info.json'), 'w', encoding='utf-8') as f:
            json.dump(os_info, f, indent=2)

        # Code version
        if run.code_version:
            if run.code_version.repo_url:
                with open(os.path.join(code_dir, 'repo_url.txt'), 'w', encoding='utf-8') as f:
                    f.write(run.code_version.repo_url)
            with open(os.path.join(code_dir, 'commit.txt'), 'w', encoding='utf-8') as f:
                f.write(run.code_version.commit_hash)
            if run.code_version.branch:
                with open(os.path.join(code_dir, 'branch.txt'), 'w', encoding='utf-8') as f:
                    f.write(run.code_version.branch)
            if run.code_version.patch_path and os.path.exists(run.code_version.patch_path):
                shutil.copy2(run.code_version.patch_path, os.path.join(code_dir, 'patch.diff'))

        # Datasets
        for rd in run.datasets:
            ds_meta_name = f'dataset-{rd.dataset.id}-{safe_name(rd.dataset.name)}-{rd.dataset.version or "na"}.meta.json'
            with open(os.path.join(ds_dir, ds_meta_name), 'w', encoding='utf-8') as f:
                json.dump(rd.dataset.to_dict(), f, indent=2)
            # Copy local snapshot or dataset file if available
            candidate = rd.snapshot_path or rd.dataset.local_path
            if candidate and os.path.exists(candidate):
                target_name = f'dataset-{rd.dataset.id}-{os.path.basename(candidate)}'
                shutil.copy2(candidate, os.path.join(ds_dir, target_name))

        # Artifacts
        for a in run.artifacts:
            if a.path and os.path.exists(a.path):
                target_name = f'artifact-{a.id}-{os.path.basename(a.path)}'
                shutil.copy2(a.path, os.path.join(arts_dir, target_name))

        # Manifest
        manifest = build_manifest(run)
        manifest_path = os.path.join(tmpdir, 'manifest.json')
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)

        # Checksums index
        checksums = {}
        for root, _, files in os.walk(tmpdir):
            for file in files:
                fp = os.path.join(root, file)
                rel = os.path.relpath(fp, tmpdir)
                checksums[rel] = sha256_of_file(fp)
        with open(os.path.join(tmpdir, 'CHECKSUMS.sha256.json'), 'w', encoding='utf-8') as f:
            json.dump(checksums, f, indent=2)

        # Zip it
        bundle_name = f'run-{run.id}-bundle-{int(time.time())}'
        out_zip = shutil.make_archive(base_name=os.path.join(bundles_dir, bundle_name), format='zip', root_dir=tmpdir)
        checksum = sha256_of_file(out_zip)
        size = os.path.getsize(out_zip)
        return out_zip, checksum, size
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def safe_name(name: str) -> str:
    return ''.join(c if c.isalnum() or c in ('-', '_') else '-' for c in (name or '')) or 'noname'

