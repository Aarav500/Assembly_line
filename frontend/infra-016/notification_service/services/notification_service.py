from __future__ import annotations
from typing import Dict
from notification_service.config import Settings
from notification_service.schemas import EmailPayload, SMSPayload, PushPayload, SendResult
from notification_service.providers.base import (
    AbstractEmailProvider, AbstractSMSProvider, AbstractPushProvider, ProviderError
)
from notification_service.providers.email.log import LogEmailProvider
from notification_service.providers.email.smtp_provider import SmtpEmailProvider
from notification_service.providers.email.sendgrid_provider import SendGridEmailProvider
from notification_service.providers.sms.log import LogSMSProvider
from notification_service.providers.sms.twilio_provider import TwilioSMSProvider
from notification_service.providers.push.log import LogPushProvider
from notification_service.providers.push.fcm_provider import FCMPushProvider


class NotificationService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._email_provider: AbstractEmailProvider | None = None
        self._sms_provider: AbstractSMSProvider | None = None
        self._push_provider: AbstractPushProvider | None = None

    def email_provider(self) -> AbstractEmailProvider:
        if self._email_provider is not None:
            return self._email_provider
        p = (self.settings.email_provider or 'log').lower()
        if p == 'smtp':
            if not self.settings.smtp_host:
                raise ProviderError('SMTP provider selected but SMTP_HOST not configured')
            self._email_provider = SmtpEmailProvider(
                host=self.settings.smtp_host,
                port=self.settings.smtp_port,
                username=self.settings.smtp_username,
                password=self.settings.smtp_password,
                use_tls=self.settings.smtp_use_tls,
                use_ssl=self.settings.smtp_use_ssl,
                default_from=self.settings.smtp_from_email,
            )
        elif p == 'sendgrid':
            if not self.settings.sendgrid_api_key:
                raise ProviderError('SendGrid provider selected but SENDGRID_API_KEY not configured')
            self._email_provider = SendGridEmailProvider(
                api_key=self.settings.sendgrid_api_key,
                default_from=self.settings.sendgrid_from_email,
            )
        else:
            self._email_provider = LogEmailProvider()
        return self._email_provider

    def sms_provider(self) -> AbstractSMSProvider:
        if self._sms_provider is not None:
            return self._sms_provider
        p = (self.settings.sms_provider or 'log').lower()
        if p == 'twilio':
            if not (self.settings.twilio_account_sid and self.settings.twilio_auth_token):
                raise ProviderError('Twilio provider selected but credentials not configured')
            self._sms_provider = TwilioSMSProvider(
                account_sid=self.settings.twilio_account_sid,
                auth_token=self.settings.twilio_auth_token,
                default_from_number=self.settings.twilio_from_number,
            )
        else:
            self._sms_provider = LogSMSProvider()
        return self._sms_provider

    def push_provider(self) -> AbstractPushProvider:
        if self._push_provider is not None:
            return self._push_provider
        p = (self.settings.push_provider or 'log').lower()
        if p == 'fcm':
            if not self.settings.fcm_server_key:
                raise ProviderError('FCM provider selected but FCM_SERVER_KEY not configured')
            self._push_provider = FCMPushProvider(server_key=self.settings.fcm_server_key)
        else:
            self._push_provider = LogPushProvider()
        return self._push_provider

    def send_email(self, payload: EmailPayload) -> SendResult:
        provider = self.email_provider()
        return provider.send(payload)

    def send_sms(self, payload: SMSPayload) -> SendResult:
        provider = self.sms_provider()
        return provider.send(payload)

    def send_push(self, payload: PushPayload) -> SendResult:
        provider = self.push_provider()
        return provider.send(payload)

