import time
from urllib.parse import urlencode
from typing import Dict, Any
import requests
from .base import BaseScanner


class ZapScanner(BaseScanner):
    name = "zap"

    def __init__(self, api_url: str, api_key: str | None = None, context_name: str | None = None, poll_interval: int = 5, max_duration: int = 900):
        if api_url.endswith('/'):
            api_url = api_url[:-1]
        self.base = api_url
        self.api_key = api_key
        self.context_name = context_name
        self.poll_interval = poll_interval
        self.max_duration = max_duration

    def _params(self, extra: dict | None = None) -> dict:
        p = {}
        if self.api_key:
            p['apikey'] = self.api_key
        if extra:
            p.update(extra)
        return p

    def _get(self, path: str, params: dict | None = None):
        url = f"{self.base}{path}"
        r = requests.get(url, params=self._params(params), timeout=30)
        r.raise_for_status()
        return r.json()

    def _action(self, path: str, params: dict | None = None):
        # ZAP uses GET for actions too
        return self._get(path, params)

    def scan(self, target_url: str) -> Dict[str, Any]:
        start = time.time()
        # Spider
        spider = self._action('/JSON/spider/action/scan/', {
            'url': target_url,
            'recurse': True,
            'contextName': self.context_name or '',
        })
        spider_scan_id = spider.get('scan') or spider.get('scanid') or spider.get('scanId')
        self._wait_status('/JSON/spider/view/status/', spider_scan_id)

        # Active Scan
        ascan = self._action('/JSON/ascan/action/scan/', {
            'url': target_url,
            'recurse': True,
            'inScopeOnly': False,
            'contextName': self.context_name or '',
        })
        ascan_id = ascan.get('scan') or ascan.get('scanid') or ascan.get('scanId')
        self._wait_status('/JSON/ascan/view/status/', ascan_id)

        # Alerts
        alerts_resp = self._get('/JSON/alert/view/alerts/', {'start': 0, 'count': 999999})
        alerts = alerts_resp.get('alerts', [])
        findings = []
        for a in alerts:
            findings.append({
                'id': a.get('pluginId') or a.get('alertRef'),
                'name': a.get('alert'),
                'severity': (a.get('risk') or 'info').lower(),
                'description': a.get('description'),
                'url': a.get('url'),
                'confidence': (a.get('confidence') or 'medium').lower(),
                'cwe': a.get('cweid'),
                'wasc': a.get('wascid'),
                'solution': a.get('solution'),
            })
        duration = int(time.time() - start)
        return {
            'target': target_url,
            'scanner': self.name,
            'duration_sec': duration,
            'findings': self.normalize_findings(findings)
        }

    def _wait_status(self, status_path: str, scan_id: str):
        start = time.time()
        while True:
            status = self._get(status_path, {'scanId': scan_id})
            percent = int(status.get('status') or status.get('scan') or 0)
            if percent >= 100:
                return
            if time.time() - start > self.max_duration:
                raise TimeoutError('ZAP scan timed out')
            time.sleep(self.poll_interval)

