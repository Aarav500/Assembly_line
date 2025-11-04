from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator, ValidationError


class ServerSettings(BaseModel):
    name: str = Field(default="ConfigMgmtDemo")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=5000)
    debug: bool = Field(default=False)

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        if not (0 < v < 65536):
            raise ValueError("port must be between 1 and 65535")
        return v


class LoggingSettings(BaseModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO")
    json: bool = Field(default=False)


class DatabaseSettings(BaseModel):
    url: str
    pool_size: int = Field(default=5)

    @field_validator("pool_size")
    @classmethod
    def validate_pool_size(cls, v: int) -> int:
        if v < 1:
            raise ValueError("pool_size must be >= 1")
        return v


class APISettings(BaseModel):
    key: Optional[str] = Field(default=None)


class AppConfig(BaseModel):
    app: ServerSettings
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    database: DatabaseSettings
    some_api: APISettings = Field(default_factory=APISettings)


__all__ = ["AppConfig", "ServerSettings", "LoggingSettings", "DatabaseSettings", "APISettings", "ValidationError"]

