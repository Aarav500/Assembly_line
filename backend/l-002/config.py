import os
from dotenv import load_dotenv

load_dotenv()


def env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.lower() in ['1', 'true', 'yes', 'on']


class Config:
    DEBUG = env_bool('DEBUG', True)
    PORT = int(os.getenv('PORT', '5000'))

    # Secrets provider: memory or vault
    SECRETS_PROVIDER = os.getenv('SECRETS_PROVIDER', 'memory').lower()

    # Memory provider seed file
    SEED_FILE = os.getenv('SEED_FILE', 'seed_secrets.yaml')

    # Policy file
    POLICY_FILE = os.getenv('POLICY_FILE', 'policies.yaml')

    # Vault settings (if using vault)
    VAULT_ADDR = os.getenv('VAULT_ADDR', '')
    VAULT_TOKEN = os.getenv('VAULT_TOKEN', '')
    VAULT_KV_MOUNT = os.getenv('VAULT_KV_MOUNT', 'secret')
    VAULT_NAMESPACE = os.getenv('VAULT_NAMESPACE', '')

    # Audit
    AUDIT_ENABLED = env_bool('AUDIT_ENABLED', True)

