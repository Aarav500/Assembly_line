from dataclasses import dataclass
from typing import Optional

@dataclass
class WikiContent:
    id: Optional[str]
    title: str
    markdown: str
    source_url: Optional[str] = None
    last_updated: Optional[str] = None
    tags: Optional[list] = None

