import os
import json
from typing import Dict, Any

TRUE_VALUES = {'1', 'true', 'yes', 'on', 'y'}

def _bool_env(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return str(val).strip().lower() in TRUE_VALUES

def _json_env(name: str, default: Dict[str, str]) -> Dict[str, str]:
    val = os.getenv(name)
    if not val:
        return default
    try:
        parsed = json.loads(val)
        if isinstance(parsed, dict):
            return {str(k): str(v) for k, v in parsed.items()}
        return default
    except Exception:
        return default

def load_config() -> Dict[str, Any]:
    cfg = {
        'STAGING_REGISTRY': os.getenv('STAGING_REGISTRY', ''),
        'STAGING_USERNAME': os.getenv('STAGING_USERNAME', ''),
        'STAGING_PASSWORD': os.getenv('STAGING_PASSWORD', ''),
        'STAGING_VERIFY_TLS': _bool_env('STAGING_VERIFY_TLS', True),
        'STAGING_EXTRA_HEADERS': _json_env('STAGING_EXTRA_HEADERS', {}),

        'PROD_REGISTRY': os.getenv('PROD_REGISTRY', ''),
        'PROD_USERNAME': os.getenv('PROD_USERNAME', ''),
        'PROD_PASSWORD': os.getenv('PROD_PASSWORD', ''),
        'PROD_VERIFY_TLS': _bool_env('PROD_VERIFY_TLS', True),
        'PROD_EXTRA_HEADERS': _json_env('PROD_EXTRA_HEADERS', {}),

        'HTTP_TIMEOUT': int(os.getenv('HTTP_TIMEOUT', '60')),
    }

    required = ['STAGING_REGISTRY', 'PROD_REGISTRY']
    for key in required:
        if not cfg[key]:
            raise ValueError(f'Missing required configuration: {key}')

    return cfg

