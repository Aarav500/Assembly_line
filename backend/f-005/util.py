import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def parse_any_timestamp_ms(value: Any) -> Optional[int]:
    if value is None:
        return None
    # Numeric epoch seconds or milliseconds
    if isinstance(value, (int, float)):
        v = float(value)
        if v > 1e12:  # likely milliseconds
            return int(v)
        return int(v * 1000)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        # numeric string
        try:
            v = float(s)
            if v > 1e12:
                return int(v)
            return int(v * 1000)
        except ValueError:
            pass
        # ISO 8601
        try:
            if s.endswith('Z'):
                s2 = s[:-1] + '+00:00'
            else:
                s2 = s
            dt = datetime.fromisoformat(s2)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp() * 1000)
        except Exception:
            return None
    # Unsupported
    return None


def ms_to_iso8601(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat().replace('+00:00', 'Z')


def flatten_kv(d: Dict[str, Any], parent_key: str = '', sep: str = '.') -> Dict[str, str]:
    items: Dict[str, str] = {}
    for k, v in (d or {}).items():
        key = f"{parent_key}{sep}{k}" if parent_key else str(k)
        if isinstance(v, dict):
            items.update(flatten_kv(v, key, sep=sep))
        else:
            try:
                if isinstance(v, (list, tuple)):
                    v_str = ','.join([_to_str(x) for x in v])
                else:
                    v_str = _to_str(v)
            except Exception:
                v_str = str(v)
            items[key] = v_str
    return items


def _to_str(v: Any) -> str:
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if v is None:
        return 'null'
    return str(v)


def build_search_text(
    *,
    message: str,
    level: Optional[str] = None,
    service: Optional[str] = None,
    environment: Optional[str] = None,
    user_id: Optional[str] = None,
    request_id: Optional[str] = None,
    host: Optional[str] = None,
    app_version: Optional[str] = None,
    logger_name: Optional[str] = None,
    thread_name: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    parts = []
    if message:
        parts.append(str(message))
    def add_token(k: str, v: Optional[str]):
        if v is not None and v != '':
            parts.append(f"{k}:{v}")
    add_token('level', level)
    add_token('service', service)
    add_token('env', environment)
    add_token('user_id', user_id)
    add_token('request_id', request_id)
    add_token('host', host)
    add_token('version', app_version)
    add_token('logger', logger_name)
    add_token('thread', thread_name)

    flat_ctx = flatten_kv(context or {})
    for k, v in flat_ctx.items():
        parts.append(f"{k}:{v}")

    flat_extra = flatten_kv(extra or {})
    for k, v in flat_extra.items():
        parts.append(f"{k}:{v}")

    return ' '.join(parts)


def safe_json_dumps(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
    except Exception:
        # fallback to str
        return json.dumps({"_repr": str(obj)}, ensure_ascii=False)

