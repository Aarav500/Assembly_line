import os
import io
import tarfile
import hashlib
import shutil
import traceback
from datetime import datetime
from typing import Optional

from flask import current_app
from ..models import db, SnapshotSchedule, Snapshot


def _ensure_app_context():
    # job functions are called from APScheduler with app context provided by the caller; safeguard
    if not current_app:
        raise RuntimeError('Application context required')


def snapshot_job(schedule_id: int):
    from flask import current_app
    with current_app.app_context():
        schedule = SnapshotSchedule.query.get(schedule_id)
        if not schedule:
            return
        schedule.last_run_at = datetime.utcnow()
        db.session.commit()
        try:
            perform_snapshot(schedule)
        except Exception as e:
            # Log failure snapshot row already created inside perform_snapshot when possible
            current_app.logger.exception('Snapshot job failed for schedule %s: %s', schedule_id, e)


def queue_snapshot_now(schedule_id: int) -> str:
    from .scheduler import get_scheduler
    scheduler = get_scheduler()
    job_id = f"snapshot-now:{schedule_id}:{datetime.utcnow().timestamp()}"
    scheduler.add_job(snapshot_job, id=job_id, args=[schedule_id])
    return job_id


def perform_snapshot(schedule: SnapshotSchedule) -> Snapshot:
    src = schedule.source_path
    if not os.path.exists(src):
        snap = Snapshot(schedule_id=schedule.id, status='FAILED', log_text=f'Source path not found: {src}')
        db.session.add(snap)
        db.session.commit()
        return snap

    timestamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    base_dir = current_app.config['SNAPSHOT_DIR']
    os.makedirs(base_dir, exist_ok=True)
    filename = f"schedule-{schedule.id}-{timestamp}.tar.gz" if schedule.snapshot_format == 'tar.gz' else f"schedule-{schedule.id}-{timestamp}.tar"
    dest_path = os.path.join(base_dir, filename)

    snap = Snapshot(schedule_id=schedule.id, status='PENDING')
    db.session.add(snap)
    db.session.commit()

    log_lines = []
    try:
        mode = 'w:gz' if filename.endswith('.tar.gz') else 'w'
        with tarfile.open(dest_path, mode) as tar:
            arcname = os.path.basename(src.rstrip(os.sep)) or 'root'
            tar.add(src, arcname=arcname)
        size = os.path.getsize(dest_path)
        checksum = _sha256_file(dest_path)
        snap.path = dest_path
        snap.size_bytes = size
        snap.checksum = checksum
        snap.status = 'SUCCESS'
        log_lines.append(f'Created snapshot {dest_path} ({size} bytes)')
        db.session.commit()
        _apply_retention(schedule)
    except Exception:
        snap.status = 'FAILED'
        log_lines.append('Exception while creating snapshot:')
        log_lines.append(traceback.format_exc())
        # Cleanup partial file
        try:
            if os.path.exists(dest_path):
                os.remove(dest_path)
        except Exception:
            pass
        db.session.commit()
    finally:
        snap.log_text = '\n'.join(log_lines)
        db.session.commit()

    return snap


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _apply_retention(schedule: SnapshotSchedule):
    keep = int(schedule.retention or 0)
    if keep <= 0:
        return
    snaps = Snapshot.query.filter_by(schedule_id=schedule.id, status='SUCCESS').order_by(Snapshot.created_at.desc()).all()
    for idx, snap in enumerate(snaps):
        if idx >= keep:
            # delete file and db row
            try:
                if snap.path and os.path.exists(snap.path):
                    os.remove(snap.path)
            except Exception:
                pass
            db.session.delete(snap)
    db.session.commit()


def restore_snapshot(snapshot: Snapshot, restore_path: Optional[str] = None) -> str:
    if snapshot.status != 'SUCCESS' or not snapshot.path or not os.path.exists(snapshot.path):
        raise RuntimeError('Snapshot not available for restore')

    base_restore_dir = current_app.config['RESTORE_DIR']
    os.makedirs(base_restore_dir, exist_ok=True)
    if not restore_path:
        timestamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        restore_path = os.path.join(base_restore_dir, f'restore-{snapshot.schedule_id}-{timestamp}')
    os.makedirs(restore_path, exist_ok=False)

    with tarfile.open(snapshot.path, 'r:*') as tar:
        tar.extractall(path=restore_path)
    return restore_path

