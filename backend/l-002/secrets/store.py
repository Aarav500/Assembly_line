from typing import Any
from .providers.memory import InMemorySecretsProvider
try:
    from .providers.vault import VaultSecretsProvider
except Exception:  # hvac may not be installed
    VaultSecretsProvider = None


def get_secrets_provider(config: Any):
    provider_name = getattr(config, 'SECRETS_PROVIDER', 'memory').lower()
    if provider_name == 'vault':
        if VaultSecretsProvider is None:
            raise RuntimeError('Vault provider requested but hvac is not installed')
        return VaultSecretsProvider(
            addr=config.VAULT_ADDR,
            token=config.VAULT_TOKEN,
            kv_mount=config.VAULT_KV_MOUNT,
            namespace=config.VAULT_NAMESPACE or None,
        )
    # default to memory
    return InMemorySecretsProvider(seed_file=getattr(config, 'SEED_FILE', None))

