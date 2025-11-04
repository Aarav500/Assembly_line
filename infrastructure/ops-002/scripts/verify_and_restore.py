#!/usr/bin/env python3
import os
import sys
import json
import tarfile
import tempfile
import pathlib
import random
import shutil
import subprocess
from typing import List, Dict, Any

from lib.common import (
    load_config,
    setup_logger,
    list_backups,
    compute_sha256,
    run_openssl_decrypt,
)


def select_backups(backups: List[Dict[str, Any]], test_backups: int, random_sample: int) -> List[Dict[str, Any]]:
    selected = backups[: max(0, test_backups)]
    remaining = backups[max(0, test_backups):]
    if random_sample > 0 and remaining:
        k = min(random_sample, len(remaining))
        selected += random.sample(remaining, k)
    # ensure unique by enc_path
    seen = set()
    unique = []
    for b in selected:
        if b['enc_path'] in seen:
            continue
        seen.add(b['enc_path'])
        unique.append(b)
    return unique


def verify_and_restore_one(cfg: Dict[str, Any], log, backup: Dict[str, Any]) -> Dict[str, Any]:
    enc_path = backup['enc_path']
    meta_path = backup['meta_path']
    result = {
        'enc_path': enc_path,
        'meta_path': meta_path,
        'ok': False,
        'errors': [],
        'restored_to': None,
    }

    if not os.path.exists(meta_path):
        msg = f"Metadata not found for {enc_path}"
        log.error(msg)
        result['errors'].append(msg)
        return result

    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)
    except Exception as e:
        msg = f"Failed to load metadata for {enc_path}: {e}"
        log.error(msg)
        result['errors'].append(msg)
        return result

    # Verify encrypted SHA
    try:
        enc_sha_actual = compute_sha256(enc_path)
        enc_sha_meta = meta.get('encrypted_sha256')
        if enc_sha_meta and enc_sha_meta != enc_sha_actual:
            msg = f"Encrypted SHA mismatch for {enc_path}: meta={enc_sha_meta} actual={enc_sha_actual}"
            log.error(msg)
            result['errors'].append(msg)
            return result
        else:
            log.info(f"Encrypted SHA verified for {enc_path}")
    except Exception as e:
        msg = f"Failed to compute SHA for {enc_path}: {e}"
        log.error(msg)
        result['errors'].append(msg)
        return result

    # Decrypt to temp
    verify_cfg = cfg['verify']
    backup_cfg = cfg['backup']
    enc_cfg = backup_cfg.get('encryption', {})
    cipher = enc_cfg.get('openssl_cipher', 'aes-256-cbc')
    key_file = enc_cfg.get('key_file', '')

    tmp_dir = tempfile.mkdtemp(prefix='restore_', dir=verify_cfg['restore_test_target'])
    os.makedirs(tmp_dir, exist_ok=True)
    dec_tar = os.path.join(tmp_dir, pathlib.Path(enc_path).name.replace('.enc', ''))

    try:
        if enc_cfg.get('enabled', True):
            run_openssl_decrypt(enc_path, dec_tar, key_file, cipher=cipher)
        else:
            # no encryption: copy file as if dec_tar is the original tar
            shutil.copyfile(enc_path, dec_tar)
        log.info(f"Decrypted to {dec_tar}")
    except Exception as e:
        msg = f"Decryption failed for {enc_path}: {e}"
        log.error(msg)
        result['errors'].append(msg)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return result

    # Verify plaintext SHA
    try:
        plain_sha_actual = compute_sha256(dec_tar)
        plain_sha_meta = meta.get('plaintext_sha256')
        if plain_sha_meta and plain_sha_meta != plain_sha_actual:
            msg = f"Plaintext SHA mismatch for {enc_path}: meta={plain_sha_meta} actual={plain_sha_actual}"
            log.error(msg)
            result['errors'].append(msg)
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return result
        else:
            log.info(f"Plaintext SHA verified for {enc_path}")
    except Exception as e:
        msg = f"Failed to compute plaintext SHA for {enc_path}: {e}"
        log.error(msg)
        result['errors'].append(msg)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return result

    # Extract
    restore_root = os.path.join(tmp_dir, 'restore')
    os.makedirs(restore_root, exist_ok=True)
    try:
        with tarfile.open(dec_tar, 'r:gz') as t:
            t.extractall(restore_root)
        log.info(f"Extracted to {restore_root}")
    except Exception as e:
        msg = f"Failed to extract tar for {enc_path}: {e}"
        log.error(msg)
        result['errors'].append(msg)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return result

    # Sentinel checks
    failed_sentinels = []
    for rel in verify_cfg.get('sentinel_paths', []):
        candidate = os.path.join(restore_root, rel)
        if not os.path.exists(candidate):
            failed_sentinels.append(rel)
    if failed_sentinels:
        msg = f"Missing sentinel paths: {', '.join(failed_sentinels)}"
        log.error(msg)
        result['errors'].append(msg)
        if not verify_cfg.get('keep_restore', False):
            shutil.rmtree(tmp_dir, ignore_errors=True)
        return result

    # Optional post-restore command
    cmd = verify_cfg.get('post_restore_cmd')
    if cmd:
        env = os.environ.copy()
        env['RESTORE_DIR'] = restore_root
        try:
            log.info(f"Running post-restore command: {cmd}")
            proc = subprocess.run(cmd, shell=True, cwd=restore_root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if proc.returncode != 0:
                msg = f"Post-restore command failed rc={proc.returncode}: {proc.stderr.strip()}"
                log.error(msg)
                result['errors'].append(msg)
                if not verify_cfg.get('keep_restore', False):
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                return result
            else:
                log.info("Post-restore command succeeded")
        except Exception as e:
            msg = f"Post-restore command exception: {e}"
            log.error(msg)
            result['errors'].append(msg)
            if not verify_cfg.get('keep_restore', False):
                shutil.rmtree(tmp_dir, ignore_errors=True)
            return result

    # Success
    result['ok'] = True
    result['restored_to'] = restore_root

    # Cleanup decrypted tar
    try:
        os.remove(dec_tar)
    except Exception:
        pass

    # Cleanup restore directory if not keeping
    if not verify_cfg.get('keep_restore', False):
        shutil.rmtree(tmp_dir, ignore_errors=True)
        result['restored_to'] = None

    return result


def main() -> int:
    cfg_path = sys.argv[1] if len(sys.argv) > 1 else None
    cfg = load_config(cfg_path)

    log = setup_logger(cfg['logging'].get('log_file'), cfg['logging'].get('level', 'INFO'))

    dest = cfg['backup']['destination']
    ensure_dir = os.makedirs
    os.makedirs(cfg['verify']['restore_test_target'], exist_ok=True)

    backups = list_backups(dest)
    if not backups:
        log.warning('No backups found to verify')
        return 0

    to_test = select_backups(backups, cfg['verify']['test_backups'], cfg['verify']['random_sample'])

    summary = {'tested': 0, 'ok': 0, 'failed': 0, 'details': []}

    for b in to_test:
        log.info(f"Verifying backup: {b['enc_path']}")
        res = verify_and_restore_one(cfg, log, b)
        summary['tested'] += 1
        if res['ok']:
            summary['ok'] += 1
            log.info(f"Verification OK: {b['enc_path']}")
        else:
            summary['failed'] += 1
            log.error(f"Verification FAILED: {b['enc_path']} -> {res['errors']}")
        summary['details'].append(res)

    # Write a report next to backups
    report_path = os.path.join(dest, 'verification_report.json')
    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
        log.info(f"Wrote verification report to {report_path}")
    except Exception:
        pass

    if summary['failed'] > 0:
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

