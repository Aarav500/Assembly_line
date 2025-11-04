import requests
from typing import Optional
from notification_service.providers.base import AbstractSMSProvider, ProviderError
from notification_service.schemas import SMSPayload, SendResult


class TwilioSMSProvider(AbstractSMSProvider):
    name = 'twilio'

    def __init__(self, account_sid: str, auth_token: str, default_from_number: Optional[str] = None):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.default_from_number = default_from_number
        self.endpoint = f'https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json'

    def send(self, message: SMSPayload) -> SendResult:
        from_number = message.from_number or self.default_from_number
        if not from_number:
            raise ProviderError('Twilio from_number is required')

        data = {
            'To': message.to,
            'From': from_number,
            'Body': message.text
        }
        try:
            resp = requests.post(self.endpoint, data=data, auth=(self.account_sid, self.auth_token), timeout=15)
            if resp.status_code in (200, 201):
                rid = None
                try:
                    rid = resp.json().get('sid')
                except Exception:
                    pass
                return SendResult(success=True, provider=self.name, message_id=rid)
            raise ProviderError(f'Twilio error {resp.status_code}: {resp.text}')
        except requests.RequestException as e:
            raise ProviderError(str(e))

