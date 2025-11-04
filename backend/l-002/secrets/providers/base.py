from typing import List, Optional, Any


class SecretsProvider:
    def name(self) -> str:
        raise NotImplementedError

    def get_secret(self, path: str) -> Optional[Any]:
        raise NotImplementedError

    def set_secret(self, path: str, value: Any) -> None:
        raise NotImplementedError

    def delete_secret(self, path: str) -> bool:
        raise NotImplementedError

    def list_secrets(self, prefix: str = '') -> List[str]:
        raise NotImplementedError

