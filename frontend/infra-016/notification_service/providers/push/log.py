import logging
from notification_service.providers.base import AbstractPushProvider
from notification_service.schemas import PushPayload, SendResult


logger = logging.getLogger(__name__)


class LogPushProvider(AbstractPushProvider):
    name = 'log'

    def send(self, message: PushPayload) -> SendResult:
        logger.info("[Push][Log] token=%s title=%s body=%s", message.token, message.title, message.body)
        return SendResult(success=True, provider=self.name, message_id=None)

