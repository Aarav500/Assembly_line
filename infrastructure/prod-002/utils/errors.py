from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class AppError(Exception):
    message: str
    code: str = "APP_ERROR"
    http_status: int = 500
    details: Dict[str, Any] | None = None

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.code}: {self.message}"


class ValidationError(AppError):
    def __init__(self, message: str = "Validation failed", details: Dict[str, Any] | None = None):
        super().__init__(message=message, code="VALIDATION_ERROR", http_status=422, details=details or {})


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found", details: Dict[str, Any] | None = None):
        super().__init__(message=message, code="NOT_FOUND", http_status=404, details=details or {})


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Unauthorized", details: Dict[str, Any] | None = None):
        super().__init__(message=message, code="UNAUTHORIZED", http_status=401, details=details or {})


class TransientError(AppError):
    def __init__(self, message: str = "Transient error", details: Dict[str, Any] | None = None):
        super().__init__(message=message, code="TRANSIENT_ERROR", http_status=503, details=details or {})

