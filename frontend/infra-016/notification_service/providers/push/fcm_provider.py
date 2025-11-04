import requests
from notification_service.providers.base import AbstractPushProvider, ProviderError
from notification_service.schemas import PushPayload, SendResult


class FCMPushProvider(AbstractPushProvider):
    name = 'fcm'

    def __init__(self, server_key: str):
        self.server_key = server_key
        # Using legacy endpoint for simplicity
        self.endpoint = 'https://fcm.googleapis.com/fcm/send'

    def send(self, message: PushPayload) -> SendResult:
        headers = {
            'Authorization': f'key={self.server_key}',
            'Content-Type': 'application/json'
        }
        body = {
            'to': message.token,
        }
        notification = {}
        if message.title is not None:
            notification['title'] = message.title
        if message.body is not None:
            notification['body'] = message.body
        if notification:
            body['notification'] = notification
        if message.data is not None:
            body['data'] = message.data
        try:
            resp = requests.post(self.endpoint, json=body, headers=headers, timeout=15)
            if resp.status_code == 200:
                rid = None
                try:
                    rid = resp.json().get('message_id')
                except Exception:
                    pass
                return SendResult(success=True, provider=self.name, message_id=str(rid) if rid else None)
            raise ProviderError(f'FCM error {resp.status_code}: {resp.text}')
        except requests.RequestException as e:
            raise ProviderError(str(e))

