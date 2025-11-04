import contextvars
from typing import Optional

request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_id", default=None)
correlation_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("correlation_id", default=None)


def set_request_id(value: Optional[str]) -> None:
    request_id_var.set(value)


def get_request_id() -> Optional[str]:
    return request_id_var.get()


def set_correlation_id(value: Optional[str]) -> None:
    correlation_id_var.set(value)


def get_correlation_id() -> Optional[str]:
    return correlation_id_var.get()

