import requests
from typing import Optional, Dict, Any
from notification_service.providers.base import AbstractEmailProvider, ProviderError
from notification_service.schemas import EmailPayload, SendResult


class SendGridEmailProvider(AbstractEmailProvider):
    name = 'sendgrid'

    def __init__(self, api_key: str, default_from: Optional[str] = None):
        self.api_key = api_key
        self.default_from = default_from
        self.endpoint = 'https://api.sendgrid.com/v3/mail/send'

    def send(self, message: EmailPayload) -> SendResult:
        from_email = str(message.from_email or self.default_from or '')
        if not from_email:
            raise ProviderError('SendGrid from address is required')

        personalizations = {
            "to": [{"email": str(x)} for x in message.to]
        }
        if message.cc:
            personalizations["cc"] = [{"email": str(x)} for x in message.cc]
        if message.bcc:
            personalizations["bcc"] = [{"email": str(x)} for x in message.bcc]

        content = []
        if message.text:
            content.append({"type": "text/plain", "value": message.text})
        if message.html:
            content.append({"type": "text/html", "value": message.html})
        if not content:
            content.append({"type": "text/plain", "value": ""})

        data: Dict[str, Any] = {
            "personalizations": [personalizations],
            "from": {"email": from_email},
            "subject": message.subject,
            "content": content
        }
        if message.reply_to:
            data["reply_to"] = {"email": str(message.reply_to)}

        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        try:
            resp = requests.post(self.endpoint, json=data, headers=headers, timeout=15)
            if resp.status_code in (200, 202):
                return SendResult(success=True, provider=self.name, message_id=resp.headers.get('X-Message-Id'))
            raise ProviderError(f'SendGrid error {resp.status_code}: {resp.text}')
        except requests.RequestException as e:
            raise ProviderError(str(e))

