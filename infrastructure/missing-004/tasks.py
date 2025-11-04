from datetime import datetime
import time

from celery import Celery
from sqlalchemy.exc import SQLAlchemyError

from config import settings
from database import db_session
from models import EmailMessage
from utils.email_renderer import render_templates
from email_providers.sendgrid_provider import SendGridProvider

try:
    from email_providers.ses_provider import SESProvider
except Exception:
    SESProvider = None  # type: ignore

celery_app = Celery(
    "email_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)


def get_provider(name: str):
    if name == "sendgrid":
        return SendGridProvider()
    if name == "ses":
        if not SESProvider:
            raise RuntimeError("SES provider not available; install boto3")
        return SESProvider()
    raise ValueError(f"Unknown provider: {name}")


@celery_app.task(bind=True, max_retries=settings.MAX_RETRIES)
def send_email(self, email_id: str):
    message = db_session.get(EmailMessage, email_id)
    if not message:
        return {"error": "message not found"}

    # Do not process already terminal states
    if message.status in ("delivered", "bounced", "failed"):
        return {"status": message.status}

    try:
        message.status = "sending"
        message.last_attempt_at = datetime.utcnow()
        message.attempt_count += 1
        db_session.add(message)
        db_session.commit()

        html_body, text_body = render_templates(message.template_name, message.template_context or {})
        provider = get_provider(message.provider)
        message_id, provider_resp = provider.send(
            to_email=message.to_email,
            from_email=settings.FROM_EMAIL,
            subject=message.subject,
            html_body=html_body,
            text_body=text_body,
            tags=message.tags or [],
            metadata=message.metadata or {},
            email_id=message.id,
        )

        message.message_id = message_id or message.message_id
        message.sent_at = datetime.utcnow()
        message.status = "sent"
        db_session.add(message)
        db_session.commit()
        return {"id": message.id, "status": message.status, "provider_response": provider_resp}

    except Exception as e:  # Broad catch; in production catch specific exceptions
        db_session.rollback()
        # Decide retry or fail
        # For demonstration, retry for any exception up to max_retries
        attempt = self.request.retries + 1
        if attempt <= settings.MAX_RETRIES:
            delay = settings.RETRY_BACKOFF_BASE * (settings.RETRY_BACKOFF_FACTOR ** (attempt - 1))
            message.error = str(e)
            message.status = "deferred"
            db_session.add(message)
            db_session.commit()
            raise self.retry(exc=e, countdown=delay)
        else:
            message.error = str(e)
            message.status = "failed"
            db_session.add(message)
            db_session.commit()
            return {"id": message.id, "status": message.status, "error": str(e)}

