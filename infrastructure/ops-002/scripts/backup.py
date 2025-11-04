#!/usr/bin/env python3
import os
import sys
import tarfile
import tempfile
import pathlib
import json
import socket
import platform
import datetime as dt
from typing import List

from lib.common import (
    load_config,
    ensure_dir,
    compute_sha256,
    setup_logger,
    openssl_available,
    run_openssl_encrypt,
    key_fingerprint,
    now_iso,
)


def tar_sources(sources: List[str], target_tar_gz: str, top_dir: str) -> None:
    with tarfile.open(target_tar_gz, mode='w:gz') as tar:
        for src in sources:
            p = pathlib.Path(src)
            if not p.exists():
                continue
            # add under top_dir/source_basename to avoid absolute paths
            arcbase = pathlib.Path(top_dir) / p.name
            tar.add(str(p), arcname=str(arcbase))


def main() -> int:
    cfg_path = sys.argv[1] if len(sys.argv) > 1 else None
    cfg = load_config(cfg_path)

    log = setup_logger(cfg['logging'].get('log_file'), cfg['logging'].get('level', 'INFO'))

    backup_cfg = cfg['backup']
    sources = backup_cfg.get('sources', [])
    if not sources:
        log.error('No sources configured for backup')
        return 1
    destination = backup_cfg['destination']
    ensure_dir(destination)

    enc_cfg = backup_cfg.get('encryption', {})
    encryption_enabled = bool(enc_cfg.get('enabled', True))
    cipher = enc_cfg.get('openssl_cipher', 'aes-256-cbc')
    key_file = enc_cfg.get('key_file', '')

    if encryption_enabled:
        if not openssl_available():
            log.error('OpenSSL not available but encryption is enabled')
            return 1
        if not key_file or not pathlib.Path(key_file).exists():
            log.error(f'Key file not found: {key_file}')
            return 1

    hostname = socket.gethostname()
    ts = dt.datetime.now().strftime('%Y%m%d_%H%M%S')
    name_prefix = backup_cfg.get('name_prefix', 'backup')
    backup_basename = f"{name_prefix}_{hostname}_{ts}"

    tar_filename = f"{backup_basename}.tar.gz"
    enc_filename = f"{tar_filename}.enc"
    sha_filename = f"{backup_basename}.sha256"
    meta_filename = f"{backup_basename}.json"

    tar_path = str(pathlib.Path(destination) / tar_filename)
    enc_path = str(pathlib.Path(destination) / enc_filename)
    sha_path = str(pathlib.Path(destination) / sha_filename)
    meta_path = str(pathlib.Path(destination) / meta_filename)

    try:
        log.info(f"Creating archive {tar_path}")
        tar_sources(sources, tar_path, top_dir=backup_basename)
        plaintext_size = os.path.getsize(tar_path)
        plaintext_sha = compute_sha256(tar_path)
        log.info(f"Plaintext TAR created size={plaintext_size} sha256={plaintext_sha}")

        encrypted_sha = ''
        encrypted_size = 0
        if encryption_enabled:
            log.info(f"Encrypting archive to {enc_path} using {cipher}")
            run_openssl_encrypt(tar_path, enc_path, key_file, cipher=cipher)
            encrypted_size = os.path.getsize(enc_path)
            encrypted_sha = compute_sha256(enc_path)
            log.info(f"Encrypted archive size={encrypted_size} sha256={encrypted_sha}")
            # Remove plaintext tar for security
            try:
                os.remove(tar_path)
                log.info("Removed plaintext tar.gz after encryption")
            except Exception as e:
                log.warning(f"Failed to remove plaintext tar: {e}")
        else:
            # If not encrypting, still treat tar as final artifact
            enc_path = tar_path
            encrypted_size = plaintext_size
            encrypted_sha = plaintext_sha

        meta = {
            'backup_name': backup_basename,
            'created_at': now_iso(),
            'hostname': hostname,
            'sources': sources,
            'plaintext_size': plaintext_size,
            'plaintext_sha256': plaintext_sha,
            'encrypted_size': encrypted_size,
            'encrypted_sha256': encrypted_sha,
            'encryption': {
                'enabled': encryption_enabled,
                'cipher': cipher if encryption_enabled else None,
                'key_file': os.path.basename(key_file) if encryption_enabled else None,
                'key_fingerprint_sha256': key_fingerprint(key_file) if encryption_enabled else None,
            },
            'artifacts': {
                'encrypted_path': enc_path,
                'sha256_path': sha_path,
            },
            'python_version': platform.python_version(),
            'platform': platform.platform(),
        }

        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2)
        log.info(f"Wrote metadata {meta_path}")

        with open(sha_path, 'w', encoding='utf-8') as f:
            f.write(f"PLAINTEXT_SHA256 {plaintext_sha} {tar_filename}\n")
            f.write(f"ENCRYPTED_SHA256 {encrypted_sha} {pathlib.Path(enc_path).name}\n")
        log.info(f"Wrote checksums {sha_path}")

    except Exception as e:
        log.exception(f"Backup failed: {e}")
        # Cleanup partial files
        for p in [tar_path, enc_path]:
            try:
                if p and os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass
        return 2

    log.info("Backup completed successfully")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

