import json
import logging
import time
from typing import Dict, Any, List
import requests


class ConsoleAlerter:
    def send(self, message: str, payload: Dict[str, Any]):
        logging.getLogger(__name__).warning('ALERT: %s\n%s', message, json.dumps(payload)[:2000])


class SlackAlerter:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, message: str, payload: Dict[str, Any]):
        data = {
            'text': message,
            'blocks': [
                {
                    'type': 'section',
                    'text': {'type': 'mrkdwn', 'text': f'*Drift Alert*\n{message}'}
                },
                {
                    'type': 'section',
                    'text': {'type': 'mrkdwn', 'text': 'Summary:```' + json.dumps(payload.get('summary', {}), indent=2) + '```'}
                }
            ]
        }
        resp = requests.post(self.webhook_url, json=data, timeout=5)
        if resp.status_code >= 300:
            raise RuntimeError(f'Slack webhook error: {resp.status_code} {resp.text}')


class AlertDispatcher:
    def __init__(self, config):
        self.config = config
        self.console = ConsoleAlerter()
        self.slack = SlackAlerter(config.SLACK_WEBHOOK_URL) if (config.ENABLE_SLACK and config.SLACK_WEBHOOK_URL) else None

    def _format_message(self, report: Dict[str, Any]) -> str:
        s = report.get('summary', {})
        sev = s.get('severity')
        feats = s.get('features_drifted', [])
        out = s.get('output_drifted', False)
        parts: List[str] = []
        parts.append(f'Severity: {sev}')
        if feats:
            parts.append(f'Feature drift: {", ".join(feats[:10])}' + ('' if len(feats) <= 10 else ' ...'))
        if out:
            parts.append('Output drift detected')
        return ' | '.join(parts)

    def send_alert(self, report: Dict[str, Any]):
        msg = self._format_message(report)
        payload = {
            'summary': report.get('summary'),
            'top_features': {k: v for k, v in list(report.get('features', {}).items())[:5]},
            'output': report.get('output', {})
        }
        # Always log to console
        self.console.send(msg, payload)
        if self.slack:
            try:
                self.slack.send(msg, payload)
            except Exception:
                logging.getLogger(__name__).exception('Failed to send Slack alert')

