from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    # Provider selection
    email_provider: str = Field(default="log", validation_alias='NOTIF_EMAIL_PROVIDER')
    sms_provider: str = Field(default="log", validation_alias='NOTIF_SMS_PROVIDER')
    push_provider: str = Field(default="log", validation_alias='NOTIF_PUSH_PROVIDER')

    # SMTP
    smtp_host: Optional[str] = Field(default=None, validation_alias='SMTP_HOST')
    smtp_port: int = Field(default=587, validation_alias='SMTP_PORT')
    smtp_username: Optional[str] = Field(default=None, validation_alias='SMTP_USERNAME')
    smtp_password: Optional[str] = Field(default=None, validation_alias='SMTP_PASSWORD')
    smtp_use_tls: bool = Field(default=True, validation_alias='SMTP_USE_TLS')
    smtp_use_ssl: bool = Field(default=False, validation_alias='SMTP_USE_SSL')
    smtp_from_email: Optional[str] = Field(default=None, validation_alias='SMTP_FROM')

    # SendGrid
    sendgrid_api_key: Optional[str] = Field(default=None, validation_alias='SENDGRID_API_KEY')
    sendgrid_from_email: Optional[str] = Field(default=None, validation_alias='SENDGRID_FROM')

    # Twilio
    twilio_account_sid: Optional[str] = Field(default=None, validation_alias='TWILIO_ACCOUNT_SID')
    twilio_auth_token: Optional[str] = Field(default=None, validation_alias='TWILIO_AUTH_TOKEN')
    twilio_from_number: Optional[str] = Field(default=None, validation_alias='TWILIO_FROM_NUMBER')

    # FCM
    fcm_server_key: Optional[str] = Field(default=None, validation_alias='FCM_SERVER_KEY')

    model_config = SettingsConfigDict(env_file='.env', extra='ignore')


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[arg-type]

