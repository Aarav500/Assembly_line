from typing import Any, Dict, List, Optional
from pydantic import BaseModel, validator
from datetime import datetime


class MetricSample(BaseModel):
    metric: str
    timestamp: Any
    value: float
    tags: Optional[Dict[str, Any]] = None

    @validator("timestamp")
    def validate_timestamp(cls, v):
        # Accept int seconds, float seconds, or ISO8601 string
        if isinstance(v, (int, float)):
            return int(v)
        if isinstance(v, str):
            try:
                # Try parse ISO8601
                dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
                return int(dt.timestamp())
            except Exception:
                # Try integer string
                try:
                    return int(float(v))
                except Exception:
                    pass
        raise ValueError("Invalid timestamp; use epoch seconds or ISO8601 string")

    def as_row(self) -> Dict[str, Any]:
        return {
            "metric": self.metric,
            "ts": int(self.timestamp),
            "value": float(self.value),
            "tags": self.tags or {},
        }


class MetricBatch(BaseModel):
    samples: List[MetricSample]

    def as_rows(self) -> List[Dict[str, Any]]:
        return [s.as_row() for s in self.samples]


class TrainRequest(BaseModel):
    metric: str
    model: str
    start_time: Optional[Any] = None
    end_time: Optional[Any] = None
    params: Optional[Dict[str, Any]] = None

    @property
    def start_ts(self) -> Optional[int]:
        return _parse_ts(self.start_time)

    @property
    def end_ts(self) -> Optional[int]:
        return _parse_ts(self.end_time)


class DetectRequest(BaseModel):
    metric: str
    model: Optional[str] = None
    threshold: Optional[float] = None
    samples: Optional[List[Dict[str, Any]]] = None
    start_time: Optional[Any] = None
    end_time: Optional[Any] = None
    limit: Optional[int] = None

    @property
    def start_ts(self) -> Optional[int]:
        return _parse_ts(self.start_time)

    @property
    def end_ts(self) -> Optional[int]:
        return _parse_ts(self.end_time)


class QueryMetricsRequest(BaseModel):
    metric: str
    start_time: Optional[Any] = None
    end_time: Optional[Any] = None
    limit: Optional[int] = None
    order: Optional[str] = "asc"

    @property
    def start_ts(self) -> Optional[int]:
        return _parse_ts(self.start_time)

    @property
    def end_ts(self) -> Optional[int]:
        return _parse_ts(self.end_time)


def _parse_ts(v: Any) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, str):
        try:
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return int(dt.timestamp())
        except Exception:
            try:
                return int(float(v))
            except Exception:
                return None
    return None

