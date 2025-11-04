import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseConnector(ABC):
    slug: str = "base"
    name: str = "Base"

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = self._check_enabled()

    @abstractmethod
    def _check_enabled(self) -> bool:
        ...

    @abstractmethod
    def health(self) -> Dict[str, Any]:
        ...

    def safe_health(self) -> Dict[str, Any]:
        try:
            if not self.enabled:
                return {"ok": False, "enabled": False, "note": "Missing or invalid config"}
            res = self.health()
            res.setdefault("ok", True)
            res["enabled"] = True
            return res
        except Exception as e:
            return {"ok": False, "enabled": self.enabled, "error": str(e)}

    def available_operations(self) -> List[str]:
        ops = []
        for attr in dir(self):
            if attr.startswith("op_") and callable(getattr(self, attr)):
                ops.append(attr.replace("op_", ""))
        # Common virtual ops
        for common in ["search", "get"]:
            if hasattr(self, common) and callable(getattr(self, common)):
                ops.append(common)
        return sorted(list(set(ops)))

    def has_operation(self, op_name: str) -> bool:
        return op_name in self.available_operations()

    def perform_action(self, action: str, params: Dict[str, Any]):
        # Try explicit op_ action first
        method_name = f"op_{action}"
        if hasattr(self, method_name):
            return getattr(self, method_name)(**params)
        # Allow calling search/get via action
        if action == "search" and hasattr(self, "search"):
            return getattr(self, "search")(params.get("q", ""))
        if action == "get" and hasattr(self, "get"):
            return getattr(self, "get")(params.get("id"))
        raise ValueError(f"Unsupported action: {action}")

    # Optional common operations
    def search(self, query: str):
        raise NotImplementedError()

    def get(self, rid: str):
        raise NotImplementedError()

