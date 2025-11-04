import os


class Config:
    # Database
    DB_PATH = os.environ.get('IR_DB_PATH', 'data/app.db')

    # Security
    API_KEY = os.environ.get('IR_API_KEY', '')  # If set, requests must include header X-API-Key

    # Providers
    ISOLATION_PROVIDER = os.environ.get('IR_ISOLATION_PROVIDER', 'dummy')  # e.g., dummy, crowdstrike, sentinelone
    KEY_REVOCATION_PROVIDER = os.environ.get('IR_KEY_REVOCATION_PROVIDER', 'dummy')  # e.g., dummy, github, aws, okta

    # Behavior
    DEFAULT_DRY_RUN = os.environ.get('IR_DEFAULT_DRY_RUN', 'false').lower() == 'true'

    # Logging
    LOG_LEVEL = os.environ.get('IR_LOG_LEVEL', 'INFO')

