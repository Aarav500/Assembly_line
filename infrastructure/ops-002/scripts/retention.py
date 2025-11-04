#!/usr/bin/env python3
import os
import sys
import json
import pathlib
import datetime as dt
from typing import List, Dict, Any

from lib.common import (
    load_config,
    setup_logger,
    list_backups,
    parse_iso,
)


def main() -> int:
    cfg_path = sys.argv[1] if len(sys.argv) > 1 else None
    cfg = load_config(cfg_path)

    log = setup_logger(cfg['logging'].get('log_file'), cfg['logging'].get('level', 'INFO'))

    dest = cfg['backup']['destination']
    backups = list_backups(dest)

    if not backups:
        log.info('No backups found for retention enforcement')
        return 0

    max_backups = cfg['retention']['max_backups']
    max_days = cfg['retention']['max_days']
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(days=max_days)

    # Determine created times
    def get_created(back: Dict[str, Any]) -> dt.datetime:
        meta_dt = parse_iso(back.get('created_at'))
        if meta_dt:
            if meta_dt.tzinfo is None:
                meta_dt = meta_dt.replace(tzinfo=dt.timezone.utc)
            return meta_dt
        # fallback to mtime
        return dt.datetime.fromtimestamp(back['mtime'], tz=dt.timezone.utc)

    # Build list with parsed times
    items = []
    for b in backups:
        items.append({
            **b,
            'created_dt': get_created(b)
        })

    # Sort newest first
    items.sort(key=lambda x: x['created_dt'], reverse=True)

    keep_set = set()
    for i, b in enumerate(items):
        if i < max_backups:
            keep_set.add(b['enc_path'])

    delete_list = []
    for i, b in enumerate(items):
        if b['enc_path'] in keep_set:
            continue
        if b['created_dt'] < cutoff:
            delete_list.append(b)

    # Perform deletions
    for b in delete_list:
        enc = b['enc_path']
        meta = b['meta_path']
        sha = b['sha_path']
        tar_plain = b['tar_path']
        for p in [enc, meta, sha, tar_plain]:
            try:
                if p and os.path.exists(p):
                    os.remove(p)
                    log.info(f"Deleted {p}")
            except Exception as e:
                log.warning(f"Failed to delete {p}: {e}")

    # Cleanup orphan metadata/sha without .enc
    dest_path = pathlib.Path(dest)
    for meta in dest_path.glob('*.json'):
        enc_candidate = dest_path / (meta.name.replace('.json', '.tar.gz.enc'))
        if not enc_candidate.exists():
            try:
                os.remove(meta)
                log.info(f"Removed orphan metadata {meta}")
            except Exception as e:
                log.warning(f"Failed to remove orphan metadata {meta}: {e}")
    for sha in dest_path.glob('*.sha256'):
        enc_candidate = dest_path / (sha.name.replace('.sha256', '.tar.gz.enc'))
        if not enc_candidate.exists():
            try:
                os.remove(sha)
                log.info(f"Removed orphan checksum {sha}")
            except Exception as e:
                log.warning(f"Failed to remove orphan checksum {sha}: {e}")

    log.info(f"Retention enforcement complete. Deleted {len(delete_list)} old backup(s).")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

