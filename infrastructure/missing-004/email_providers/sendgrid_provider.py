from typing import List, Optional, Dict, Tuple
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, Personalization
from config import settings


class SendGridProvider:
    def __init__(self, api_key: Optional[str] = None):
        self.client = SendGridAPIClient(api_key or settings.SENDGRID_API_KEY)

    def send(
        self,
        *,
        to_email: str,
        from_email: str,
        subject: str,
        html_body: str,
        text_body: str,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict] = None,
        email_id: Optional[str] = None,
    ) -> Tuple[str, Dict]:
        mail = Mail()
        mail.from_email = Email(from_email)
        mail.subject = subject
        personalization = Personalization()
        personalization.add_to(To(to_email))
        # Set custom args for event correlation
        if email_id:
            personalization.custom_args = {"email_id": email_id}
        if tags:
            # SendGrid categories for tagging
            for tag in tags:
                mail.add_category(tag)
        if metadata:
            personalization.dynamic_template_data = metadata
        mail.add_personalization(personalization)
        mail.add_content(Content("text/plain", text_body))
        mail.add_content(Content("text/html", html_body))

        response = self.client.send(mail)
        # SendGrid returns message id in header 'X-Message-Id' or 'X-Message-ID' or sg-message-id
        message_id = (
            response.headers.get("X-Message-Id")
            or response.headers.get("X-Message-ID")
            or response.headers.get("X-Message-Id".lower())
            or response.headers.get("SG-Message-Id")
            or ""
        )
        return message_id, {"status_code": response.status_code, "headers": dict(response.headers)}

