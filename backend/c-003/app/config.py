import os


def _str_to_bool(val: str | None, default: bool = False) -> bool:
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    DEBUG = _str_to_bool(os.getenv("FLASK_DEBUG"), False)
    TESTING = False
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "8000"))
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class ProductionConfig(BaseConfig):
    DEBUG = False


class TestingConfig(BaseConfig):
    TESTING = True
    DEBUG = True


def get_config(name: str | None = None):
    env = (name or os.getenv("FLASK_ENV") or os.getenv("APP_ENV") or "production").lower()
    mapping = {
        "development": DevelopmentConfig,
        "dev": DevelopmentConfig,
        "production": ProductionConfig,
        "prod": ProductionConfig,
        "testing": TestingConfig,
        "test": TestingConfig,
    }
    return mapping.get(env, ProductionConfig)

