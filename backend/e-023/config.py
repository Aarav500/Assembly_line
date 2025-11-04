import yaml
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ValidationError


class ConfigError(Exception):
    pass


class MetricsConfig(BaseModel):
    type: str = Field(description="metrics source type: redis|prometheus|mock")
    metric_id: str = Field(description="identifier for the queue metric (e.g. key name, prom series)")
    params: Dict[str, Any] = Field(default_factory=dict)


class BatchWindow(BaseModel):
    name: Optional[str] = None
    timezone: str = "UTC"
    days: Optional[List[str]] = None  # e.g., ["Mon","Tue"] or None for all
    start: str  # HH:MM
    end: str  # HH:MM
    min_gpus: int = 0
    lead_minutes: int = 0


class ScalingPolicy(BaseModel):
    name: str
    provider: str = "mock"
    provider_params: Dict[str, Any] = Field(default_factory=dict)
    pool_id: str
    min_gpus: int = 0
    max_gpus: int = 100
    target_queue_per_gpu: int = 4
    scale_step_gpus: int = 2
    cooldown_seconds: int = 300
    metrics: MetricsConfig
    batch_windows: List[BatchWindow] = Field(default_factory=list)
    tags: Dict[str, str] = Field(default_factory=dict)


class AppConfig(BaseModel):
    policies: List[ScalingPolicy]


class ConfigLoader:
    def load(self, path: str) -> AppConfig:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            return self.from_dict(data)
        except FileNotFoundError:
            raise ConfigError(f"Config file not found: {path}")
        except ValidationError as ve:
            raise ConfigError(str(ve))
        except Exception as e:
            raise ConfigError(str(e))

    def from_dict(self, data: Dict[str, Any]) -> AppConfig:
        try:
            return AppConfig(**data)
        except ValidationError as ve:
            raise ConfigError(str(ve))

    def default_config(self) -> AppConfig:
        return AppConfig(policies=[
            ScalingPolicy(
                name="default",
                provider="mock",
                pool_id="gpu-pool-a",
                min_gpus=0,
                max_gpus=16,
                target_queue_per_gpu=4,
                scale_step_gpus=2,
                cooldown_seconds=120,
                metrics=MetricsConfig(type="mock", metric_id="default", params={"mode": "triangular", "min": 0, "max": 64, "period_seconds": 600}),
                batch_windows=[
                    BatchWindow(name="night-train", timezone="UTC", days=["Mon","Tue","Wed","Thu","Fri"], start="00:00", end="06:00", min_gpus=8, lead_minutes=15)
                ],
                tags={"env": "dev"}
            )
        ])

