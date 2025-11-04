from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional
from notification_service.schemas import SendResult, EmailPayload, SMSPayload, PushPayload


class ProviderError(Exception):
    pass


class AbstractProvider(ABC):
    name: str = 'abstract'


class AbstractEmailProvider(AbstractProvider, ABC):
    name: str = 'email-abstract'

    @abstractmethod
    def send(self, message: EmailPayload) -> SendResult:
        raise NotImplementedError


class AbstractSMSProvider(AbstractProvider, ABC):
    name: str = 'sms-abstract'

    @abstractmethod
    def send(self, message: SMSPayload) -> SendResult:
        raise NotImplementedError


class AbstractPushProvider(AbstractProvider, ABC):
    name: str = 'push-abstract'

    @abstractmethod
    def send(self, message: PushPayload) -> SendResult:
        raise NotImplementedError

