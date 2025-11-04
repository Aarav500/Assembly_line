import logging
from notification_service.providers.base import AbstractSMSProvider
from notification_service.schemas import SMSPayload, SendResult


logger = logging.getLogger(__name__)


class LogSMSProvider(AbstractSMSProvider):
    name = 'log'

    def send(self, message: SMSPayload) -> SendResult:
        logger.info("[SMS][Log] to=%s text=%s", message.to, message.text)
        return SendResult(success=True, provider=self.name, message_id=None, metadata={"to": message.to})

