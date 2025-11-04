import os
from dataclasses import dataclass


@dataclass
class AppConfig:
    SERVICE_NAME: str = "template-flask-service"
    SERVICE_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "dev"

    LOG_LEVEL: str = "INFO"

    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://otel-collector:4317"  # gRPC
    OTEL_EXPORTER_OTLP_PROTOCOL: str = "grpc"  # grpc | http/protobuf
    OTEL_TRACES_SAMPLER: str = "parentbased_traceidratio"
    OTEL_TRACES_SAMPLER_ARG: str = "1.0"  # 100% by default for demo

    METRICS_ENABLED: bool = True
    TRACING_ENABLED: bool = True

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            SERVICE_NAME=os.getenv("SERVICE_NAME", cls.SERVICE_NAME),
            SERVICE_VERSION=os.getenv("SERVICE_VERSION", cls.SERVICE_VERSION),
            ENVIRONMENT=os.getenv("ENVIRONMENT", cls.ENVIRONMENT),
            LOG_LEVEL=os.getenv("LOG_LEVEL", cls.LOG_LEVEL),
            OTEL_EXPORTER_OTLP_ENDPOINT=os.getenv(
                "OTEL_EXPORTER_OTLP_ENDPOINT", cls.OTEL_EXPORTER_OTLP_ENDPOINT
            ),
            OTEL_EXPORTER_OTLP_PROTOCOL=os.getenv(
                "OTEL_EXPORTER_OTLP_PROTOCOL", cls.OTEL_EXPORTER_OTLP_PROTOCOL
            ),
            OTEL_TRACES_SAMPLER=os.getenv(
                "OTEL_TRACES_SAMPLER", cls.OTEL_TRACES_SAMPLER
            ),
            OTEL_TRACES_SAMPLER_ARG=os.getenv(
                "OTEL_TRACES_SAMPLER_ARG", cls.OTEL_TRACES_SAMPLER_ARG
            ),
            METRICS_ENABLED=os.getenv("METRICS_ENABLED", str(cls.METRICS_ENABLED)).lower()
            in ("1", "true", "yes"),
            TRACING_ENABLED=os.getenv("TRACING_ENABLED", str(cls.TRACING_ENABLED)).lower()
            in ("1", "true", "yes"),
        )

