import smtplib
from email.message import EmailMessage
from typing import Optional
import ssl
from notification_service.schemas import EmailPayload, SendResult
from notification_service.providers.base import AbstractEmailProvider, ProviderError


class SmtpEmailProvider(AbstractEmailProvider):
    name = 'smtp'

    def __init__(self, host: str, port: int = 587, username: Optional[str] = None, password: Optional[str] = None,
                 use_tls: bool = True, use_ssl: bool = False, default_from: Optional[str] = None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.use_ssl = use_ssl
        self.default_from = default_from

    def _build_message(self, payload: EmailPayload) -> EmailMessage:
        msg = EmailMessage()
        from_email = payload.from_email or self.default_from
        if not from_email:
            raise ProviderError('SMTP from address is required')
        msg['From'] = str(from_email)
        msg['To'] = ', '.join([str(x) for x in payload.to])
        if payload.cc:
            msg['Cc'] = ', '.join([str(x) for x in payload.cc])
        if payload.bcc:
            # BCC isn't added as header for privacy; handle in recipients list
            pass
        if payload.reply_to:
            msg['Reply-To'] = str(payload.reply_to)
        msg['Subject'] = payload.subject

        if payload.html and payload.text:
            msg.set_content(payload.text)
            msg.add_alternative(payload.html, subtype='html')
        elif payload.html:
            msg.add_alternative(payload.html, subtype='html')
        elif payload.text:
            msg.set_content(payload.text)
        else:
            msg.set_content('')
        return msg

    def send(self, message: EmailPayload) -> SendResult:
        msg = self._build_message(message)
        recipients = [str(x) for x in message.to]
        if message.cc:
            recipients.extend([str(x) for x in message.cc])
        if message.bcc:
            recipients.extend([str(x) for x in message.bcc])

        try:
            if self.use_ssl:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.host, self.port, context=context) as server:
                    if self.username and self.password:
                        server.login(self.username, self.password)
                    server.send_message(msg, to_addrs=recipients)
            else:
                with smtplib.SMTP(self.host, self.port) as server:
                    if self.use_tls:
                        server.starttls()
                    if self.username and self.password:
                        server.login(self.username, self.password)
                    server.send_message(msg, to_addrs=recipients)
            return SendResult(success=True, provider=self.name, message_id=None, metadata={"recipients": recipients})
        except Exception as e:
            raise ProviderError(str(e))

