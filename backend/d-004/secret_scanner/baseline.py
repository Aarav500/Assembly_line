import json
import hashlib
import os
from typing import Set, Dict, Any, List

class Baseline:
    def __init__(self, fingerprints: Set[str] | None = None) -> None:
        self.fingerprints: Set[str] = fingerprints or set()

    def add(self, fingerprint: str) -> None:
        self.fingerprints.add(fingerprint)

    def contains(self, fingerprint: str) -> bool:
        return fingerprint in self.fingerprints

    def to_dict(self) -> Dict[str, Any]:
        return {"fingerprints": sorted(self.fingerprints)}

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Baseline":
        fps = set(data.get("fingerprints", []))
        return Baseline(fps)

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, sort_keys=True)

    @staticmethod
    def load(path: str) -> "Baseline":
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return Baseline.from_dict(data)
            except Exception:
                return Baseline()
        return Baseline()


def fingerprint(rule_id: str, file_path: str, match: str) -> str:
    h = hashlib.sha256()
    key = f"{rule_id}|{file_path}|{match.strip()}".encode("utf-8", errors="ignore")
    h.update(key)
    return h.hexdigest()

__all__ = ["Baseline", "fingerprint"]

