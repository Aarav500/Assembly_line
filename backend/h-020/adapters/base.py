from dataclasses import dataclass
from typing import Optional, Tuple
from models.wiki_content import WikiContent

class WikiAdapterError(Exception):
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.details = details or {}

class WikiAdapter:
    def get_content(self, identifier: dict) -> WikiContent:
        raise NotImplementedError

    def upsert_content(self, identifier: dict, content: WikiContent) -> Tuple[dict, bool]:
        """
        Create or update content at target identified by identifier. Returns (resolved_identifier, created_bool)
        """
        raise NotImplementedError

    def identify(self, identifier: dict) -> dict:
        """Normalize/resolve identifier (e.g., find page_id by title)."""
        return identifier

