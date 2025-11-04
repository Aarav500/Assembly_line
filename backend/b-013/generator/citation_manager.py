import random
import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Reference:
    id: int
    key: str
    title: str
    authors: str
    year: str
    venue: str


class CitationManager:
    def __init__(self, references: List[Reference], style: str = 'numeric'):
        self.references = references[:]  # list of Reference
        self.style = style if style in ['numeric', 'author-year'] else 'numeric'
        self._by_key = {r.key: r for r in self.references}

    def all(self) -> List[Reference]:
        return self.references

    def get_random_ids(self, k: int = 1) -> List[int]:
        if not self.references:
            return []
        k = max(0, min(k, len(self.references)))
        return sorted(random.sample([r.id for r in self.references], k))

    def inline(self, ids: List[int]) -> str:
        ids = list(dict.fromkeys([i for i in ids if isinstance(i, int)]))  # dedupe, preserve order
        if not ids:
            return ''
        if self.style == 'numeric':
            return '[' + ','.join(str(i) for i in ids) + ']'
        else:
            # author-year simplified: (Author1, Year; Author2, Year)
            parts = []
            for i in ids:
                ref = next((r for r in self.references if r.id == i), None)
                if ref:
                    main_author = ref.authors.split(' and ')[0].split(',')[0].strip()
                    parts.append(f"{main_author}, {ref.year}")
            return '(' + '; '.join(parts) + ')' if parts else ''

    def format_bibliography_entry(self, ref: Reference, numeric_id: Optional[int] = None) -> str:
        aid = numeric_id if numeric_id is not None else ref.id
        # Simple formatted string; could be extended to specific styles
        author_str = ref.authors
        year_str = ref.year
        title_str = ref.title
        venue_str = ref.venue
        return f"{aid}. {author_str} ({year_str}). {title_str}. {venue_str}."

    def linkify_citations_html(self, text: str) -> str:
        # Convert [1,2] to links to #ref-1 and #ref-2
        def repl(match):
            content = match.group(1)
            parts = [p.strip() for p in content.split(',') if p.strip().isdigit()]
            links = ', '.join(f"<a href=\"#ref-{p}\">[{p}]</a>" for p in parts)
            return links if links else match.group(0)
        return re.sub(r"\[(\s*\d+(?:\s*,\s*\d+)*)\]", repl, text)

