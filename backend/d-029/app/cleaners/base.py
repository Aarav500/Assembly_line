from __future__ import annotations
from typing import TypedDict

from ..config import Settings


class CleanupResult(TypedDict, total=False):
    name: str
    ok: bool
    details: dict
    error: str


class BaseCleaner:
    def __init__(self, settings: Settings, name: str):
        self.settings = settings
        self.name = name

    def cleanup(self, ctx: dict) -> CleanupResult:
        raise NotImplementedError

    @property
    def dry_run(self) -> bool:
        return self.settings.dry_run

