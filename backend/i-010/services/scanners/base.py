from abc import ABC, abstractmethod
from typing import Dict, Any, List


class BaseScanner(ABC):
    name: str = "base"

    @abstractmethod
    def scan(self, target_url: str) -> Dict[str, Any]:
        """
        Run a scan against target_url and return a standardized result dict:
        {
            'target': str,
            'scanner': str,
            'duration_sec': int,
            'findings': [
                {
                    'id': str,
                    'name': str,
                    'severity': 'high'|'medium'|'low'|'info',
                    'description': str,
                    'url': str,
                    'confidence': 'high'|'medium'|'low',
                    'cwe': str|None,
                    'wasc': str|None,
                    'solution': str|None,
                },
                ...
            ]
        }
        """
        raise NotImplementedError

    def normalize_findings(self, findings: List[dict]) -> List[dict]:
        normalized = []
        for f in findings:
            normalized.append({
                'id': str(f.get('id') or f.get('pluginid') or f.get('alertRef') or ''),
                'name': f.get('name') or f.get('alert') or 'Finding',
                'severity': (f.get('severity') or f.get('risk') or 'info').lower(),
                'description': f.get('description') or f.get('desc') or '',
                'url': f.get('url') or f.get('instance') or f.get('uri') or '',
                'confidence': (f.get('confidence') or 'medium').lower(),
                'cwe': f.get('cweid') or f.get('cwe') or None,
                'wasc': f.get('wascid') or f.get('wasc') or None,
                'solution': f.get('solution') or f.get('remediation') or None,
            })
        return normalized

