from __future__ import annotations
import os
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
import yaml


class CheckConfig(BaseModel):
    type: str  # status_code, response_time_ms, jsonpath, contains, regex
    op: str | None = None  # eq, ne, lt, gt, lte, gte, in, regex, exists
    expected: Any | None = None
    path: str | None = None  # for jsonpath
    description: str | None = None


class StepConfig(BaseModel):
    name: str
    method: str = Field(default="GET")
    url: str
    headers: Dict[str, str] | None = None
    params: Dict[str, Any] | None = None
    data: Any | None = None
    json: Any | None = None
    timeout_sec: float | None = None
    checks: List[CheckConfig] = Field(default_factory=list)


class FlowConfig(BaseModel):
    id: str
    name: str
    enabled: bool = True
    schedule_every_sec: int = 60
    severity: str = "critical"
    alert_channels: List[str] = Field(default_factory=lambda: ["log"])
    fail_threshold: int = 1  # consecutive failures before alert
    retry_on_failure: int = 0
    retry_delay_seconds: float = 2.0
    steps: List[StepConfig]


class NotifierSettings(BaseModel):
    slack_webhook_url: Optional[str] = None
    webhook_url: Optional[str] = None
    email_host: Optional[str] = None
    email_port: Optional[int] = None
    email_tls: bool = True
    email_user: Optional[str] = None
    email_password: Optional[str] = None
    email_from: Optional[str] = None
    email_to: Optional[str] = None

    @staticmethod
    def from_env(base: "NotifierSettings") -> "NotifierSettings":
        return NotifierSettings(
            slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL", base.slack_webhook_url),
            webhook_url=os.getenv("ALERT_WEBHOOK_URL", base.webhook_url),
            email_host=os.getenv("SMTP_HOST", base.email_host),
            email_port=int(os.getenv("SMTP_PORT", str(base.email_port or "0"))) if (os.getenv("SMTP_PORT") or base.email_port) else None,
            email_tls=(os.getenv("SMTP_TLS", "true").lower() in ("1", "true", "yes")) if os.getenv("SMTP_TLS") else base.email_tls,
            email_user=os.getenv("SMTP_USER", base.email_user),
            email_password=os.getenv("SMTP_PASSWORD", base.email_password),
            email_from=os.getenv("ALERT_EMAIL_FROM", base.email_from),
            email_to=os.getenv("ALERT_EMAIL_TO", base.email_to),
        )


class AlertingConfig(BaseModel):
    default_cooldown_sec: int = 600
    notifiers: List[str] = Field(default_factory=lambda: ["log"])  # available: log, slack, email, webhook
    settings: NotifierSettings = Field(default_factory=NotifierSettings)


class AppConfig(BaseModel):
    verify_ssl: bool = True
    default_timeout_seconds: float = 10.0


class Config(BaseModel):
    database_url: Optional[str] = None
    app: AppConfig = Field(default_factory=AppConfig)
    alerting: AlertingConfig = Field(default_factory=AlertingConfig)
    flows: List[FlowConfig] = Field(default_factory=list)

    @validator("flows")
    def unique_flow_ids(cls, v):
        ids = [f.id for f in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Flow ids must be unique")
        return v


def load_config(path: str) -> Config:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    cfg = Config(**data)
    # merge env overrides for notifiers
    cfg.alerting.settings = NotifierSettings.from_env(cfg.alerting.settings)
    # database url override
    env_db = os.getenv("DATABASE_URL")
    if env_db:
        cfg.database_url = env_db
    return cfg

