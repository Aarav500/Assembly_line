import logging
from notification_service.schemas import EmailPayload, SendResult
from notification_service.providers.base import AbstractEmailProvider


logger = logging.getLogger(__name__)


class LogEmailProvider(AbstractEmailProvider):
    name = 'log'

    def send(self, message: EmailPayload) -> SendResult:
        logger.info("[Email][Log] to=%s subject=%s", ','.join([str(x) for x in message.to]), message.subject)
        return SendResult(success=True, provider=self.name, message_id=None, metadata={"to": [str(x) for x in message.to]})

