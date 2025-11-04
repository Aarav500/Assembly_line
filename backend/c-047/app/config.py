"""
Centralized configuration classes for the Flask application.

Developer explanation:
- Use class-based configs to keep related settings grouped and override selectively per environment.
- Avoid hardcoding secrets in code. Load from environment variables where appropriate.
- You can extend these classes with DB settings, CORS, cache backends, etc.
"""

from __future__ import annotations

import os
from typing import Any, Dict


class BaseConfig:
    """Base settings applied to all environments unless overridden."""

    # CORE
    ENV = "base"  # Not a Flask field, but used here for clarity
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.getenv("SECRET_KEY", "please-change-me")

    # LOGGING
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    FORCE_LOG_HANDLER = False  # Force our handler even if one exists (rarely needed)

    # EXAMPLE FEATURE FLAGS / SETTINGS
    # Enable this to include extra debug info in responses (never enable in prod)
    INCLUDE_DEBUG_META = os.getenv("INCLUDE_DEBUG_META", "false").lower() == "true"


class DevelopmentConfig(BaseConfig):
    """Development defaults: verbose logging and debug mode."""

    ENV = "development"
    DEBUG = True
    LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")
    INCLUDE_DEBUG_META = True


class TestingConfig(BaseConfig):
    """Testing defaults: designed for unit tests and CI."""

    ENV = "testing"
    TESTING = True
    DEBUG = False
    # Ensure deterministic behavior in tests (e.g., fixed secret, lower log verbosity)
    SECRET_KEY = "test-secret-key"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "WARNING")


class ProductionConfig(BaseConfig):
    """Production defaults: safer and less verbose."""

    ENV = "production"
    DEBUG = False
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


CONFIG_MAP: Dict[str, Any] = {
    "development": DevelopmentConfig,
    "dev": DevelopmentConfig,
    "testing": TestingConfig,
    "test": TestingConfig,
    "production": ProductionConfig,
    "prod": ProductionConfig,
}

