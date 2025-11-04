import time
from typing import Dict, Any
from .base import BaseScanner


class DummyScanner(BaseScanner):
    name = "dummy"

    def scan(self, target_url: str) -> Dict[str, Any]:
        start = time.time()
        time.sleep(1.0)
        findings = [
            {
                'id': 'D-001',
                'name': 'Clickjacking Protection Missing',
                'severity': 'low',
                'description': 'X-Frame-Options header not present.',
                'url': target_url,
                'confidence': 'medium',
                'cwe': 'CWE-1021',
                'wasc': 'WASC-15',
                'solution': 'Add X-Frame-Options: SAMEORIGIN or Content-Security-Policy frame-ancestors.'
            }
        ]
        return {
            'target': target_url,
            'scanner': self.name,
            'duration_sec': int(time.time() - start),
            'findings': self.normalize_findings(findings)
        }

