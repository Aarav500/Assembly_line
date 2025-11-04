from typing import Dict, Any
from flask import render_template


def render_html_report(payload: Dict[str, Any]) -> str:
    # payload contains: audit_id, timestamp_utc, config, metrics (summary), suggestions
    return render_template('report.html', payload=payload)

