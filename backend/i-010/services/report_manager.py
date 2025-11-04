from datetime import datetime
from typing import List, Dict, Any
from models import Report
from database import db


def _severity_bucket(sev: str) -> str:
    s = (sev or 'info').lower()
    if s in ('high', 'h', '3'): return 'high'
    if s in ('medium', 'm', '2'): return 'medium'
    if s in ('low', 'l', '1'): return 'low'
    return 'info'


def build_report(scan_id: str, scanner: str, target_url: str, findings: List[Dict[str, Any]]) -> Report:
    counts = {'high': 0, 'medium': 0, 'low': 0, 'info': 0}
    for f in findings:
        counts[_severity_bucket(f.get('severity'))] += 1

    summary = f"Scanner: {scanner} | Target: {target_url} | Findings: H:{counts['high']} M:{counts['medium']} L:{counts['low']} I:{counts['info']}"

    html_parts = [
        '<html><head><meta charset="utf-8"><title>Automated Penetration Test Report</title>',
        '<style>body{font-family:Arial,sans-serif;margin:20px} .sev-high{color:#b71c1c} .sev-medium{color:#e65100} .sev-low{color:#33691e} .sev-info{color:#0d47a1} table{border-collapse:collapse;width:100%} th,td{border:1px solid #ddd;padding:8px} th{background:#f7f7f7;text-align:left}</style>',
        '</head><body>'
    ]
    html_parts.append(f'<h1>Automated Penetration Test Report</h1>')
    html_parts.append(f'<p><strong>Scan ID:</strong> {scan_id}<br/><strong>Scanner:</strong> {scanner}<br/><strong>Target:</strong> {target_url}<br/><strong>Generated:</strong> {datetime.utcnow().isoformat()}Z</p>')
    html_parts.append(f"<p><strong>Summary:</strong> {summary}</p>")
    html_parts.append('<table><thead><tr><th>Severity</th><th>Name</th><th>URL</th><th>Description</th><th>CWE</th><th>Remediation</th></tr></thead><tbody>')
    for f in findings:
        sev = _severity_bucket(f.get('severity'))
        html_parts.append(
            f"<tr><td class='sev-{sev}'>{sev.upper()}</td><td>{escape_html(f.get('name'))}</td><td>{escape_html(f.get('url') or '')}</td><td>{escape_html(f.get('description') or '')}</td><td>{escape_html(str(f.get('cwe') or ''))}</td><td>{escape_html(f.get('solution') or '')}</td></tr>"
        )
    html_parts.append('</tbody></table></body></html>')
    html = ''.join(html_parts)

    report = Report(
        scan_id=scan_id,
        summary=summary,
        details={'target': target_url, 'scanner': scanner, 'findings': findings},
        html=html,
        severity_high=counts['high'],
        severity_medium=counts['medium'],
        severity_low=counts['low'],
        severity_info=counts['info'],
    )
    db.session.add(report)
    db.session.flush()
    return report


def escape_html(text: str) -> str:
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#39;'))

