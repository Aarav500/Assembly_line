import threading
from datetime import datetime
from urllib.parse import urlparse
from typing import Dict, Any, List

from database import db
from models import Scan
from services.report_manager import build_report
from services.scanners.base import BaseScanner


class ScanManager:
    def __init__(self, app, db, scanners: Dict[str, BaseScanner], allowed_targets: List[str], report_storage_path: str | None = None):
        self.app = app
        self.db = db
        self.scanners = scanners
        self.allowed_targets = [h.lower() for h in allowed_targets or []]
        self.report_storage_path = report_storage_path

    def start_scan(self, target_url: str, scanner_name: str = 'dummy', metadata: Dict[str, Any] | None = None) -> Scan:
        self._validate_target(target_url)
        scanner = self.scanners.get(scanner_name)
        if not scanner:
            raise ValueError(f"unknown_scanner: {scanner_name}")

        scan = Scan(target_url=target_url, scanner=scanner_name, status='queued', metadata=metadata or {})
        db.session.add(scan)
        db.session.commit()

        t = threading.Thread(target=self._run_scan_thread, args=(scan.id,), daemon=True)
        t.start()
        return scan

    def _validate_target(self, target_url: str):
        try:
            p = urlparse(target_url)
        except Exception:
            raise ValueError('invalid_url')
        if p.scheme not in ('http', 'https'):
            raise ValueError('invalid_url_scheme')
        host = (p.hostname or '').lower()
        if not host:
            raise ValueError('invalid_url_host')
        if not self.allowed_targets:
            raise ValueError('no_allowed_targets_configured')
        if not self._host_allowed(host):
            raise ValueError('target_not_allowed')

    def _host_allowed(self, host: str) -> bool:
        for entry in self.allowed_targets:
            if entry == '*':
                return True
            e = entry.lstrip('.').lower()
            if entry.startswith('*.'):
                # subdomain match
                if host.endswith('.' + e[2:]):
                    return True
            else:
                if host == e:
                    return True
        return False

    def _run_scan_thread(self, scan_id: str):
        with self.app.app_context():
            scan = Scan.query.get(scan_id)
            if not scan:
                return
            scan.status = 'running'
            scan.started_at = datetime.utcnow()
            db.session.commit()

            try:
                scanner: BaseScanner = self.scanners[scan.scanner]
                result = scanner.scan(scan.target_url)
                findings = result.get('findings') or []
                report = build_report(scan_id=scan.id, scanner=scan.scanner, target_url=scan.target_url, findings=findings)
                db.session.flush()

                scan.report_id = report.id
                scan.findings_count = len(findings)
                scan.status = 'completed'
                scan.finished_at = datetime.utcnow()
                db.session.commit()
            except Exception as e:
                scan.status = 'failed'
                scan.error_message = str(e)
                scan.finished_at = datetime.utcnow()
                db.session.commit()

