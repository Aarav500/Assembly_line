import re
from typing import List, Dict, Any
from .normalization import normalize_whitespace, strip_brackets

YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Z0-9]+)\b", re.I)
URL_RE = re.compile(r"https?://[^\s>]+", re.I)

SECTION_HEADER_RE = re.compile(r"(?im)^\s*(references|bibliography|works\s+cited)\s*$")

# Common reference line starters: [1] 1. Author, Author (Year) etc.
ITEM_START_RE = re.compile(r"(?im)^\s*(?:\[\d+\]|\d+\.|\d+\)|•|\-)\s+")


def _find_references_section(text: str) -> str:
    m = SECTION_HEADER_RE.search(text)
    if not m:
        return text
    start = m.end()
    return text[start:]


def _split_reference_items(ref_text: str) -> List[str]:
    # Normalize whitespace and preserve line structure
    lines = [l.rstrip() for l in ref_text.splitlines()]
    buf = []
    current = []

    def push_current():
        if current:
            item = " ".join([c.strip() for c in current if c.strip()])
            if item:
                buf.append(item)

    for line in lines:
        if not line.strip():
            # Blank line indicates potential boundary
            if current:
                push_current()
                current = []
            continue
        if ITEM_START_RE.match(line) and current:
            # New numbered/bracketed item starts
            push_current()
            current = [ITEM_START_RE.sub("", line).strip()]
        else:
            # Heuristics: end of item often at a period + year or doi
            current.append(line.strip())
            joined = " ".join(current)
            if joined.strip().endswith(".") and (YEAR_RE.search(joined) or DOI_RE.search(joined)):
                push_current()
                current = []
    if current:
        push_current()
    # Post-process: filter out too-short items
    items = [i for i in buf if len(i) > 25 and any(tok in i.lower() for tok in [",", ".", ")"]) ]
    return items


def _extract_fields(raw: str) -> Dict[str, Any]:
    raw_norm = normalize_whitespace(raw)
    doi = None
    urls = []

    doi_m = DOI_RE.search(raw_norm)
    if doi_m:
        doi = doi_m.group(1).rstrip(". )]")

    for m in URL_RE.finditer(raw_norm):
        url = m.group(0).rstrip('.,);]')
        # Deduplicate DOI URL if present
        if doi and doi.lower() in url.lower():
            continue
        urls.append(url)

    year = None
    year_m = YEAR_RE.search(raw_norm)
    if year_m:
        year = int(year_m.group(1))

    # Very light title extraction heuristic: text between year and next period
    title = None
    if year_m:
        after_year = raw_norm[year_m.end():].strip()
        # Remove leading punctuation/space
        after_year = after_year.lstrip(").,;:- ")
        # Title often ends at first period before journal
        if "." in after_year:
            title = after_year.split(".", 1)[0].strip()
            # If title looks like a URL or is too short, discard
            if len(title) < 5 or URL_RE.search(title):
                title = None

    # Authors heuristic: before year
    authors = []
    if year_m:
        before_year = raw_norm[:year_m.start()].strip()
        # Split on 'and', '&', or ';'
        cand = re.split(r"\band\b|&|;", before_year)
        authors = [strip_brackets(c).strip().strip(',') for c in cand if len(c.strip()) > 2]
        # Keep only first ~6 authors
        authors = authors[:6]

    return {
        "raw": raw_norm,
        "year": year,
        "title": title,
        "authors": authors,
        "doi": doi,
        "urls": urls,
    }


def extract_citations(text: str, options: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    options = options or {}
    ref_text = _find_references_section(text)
    items = _split_reference_items(ref_text)
    citations: List[Dict[str, Any]] = []
    for idx, item in enumerate(items, start=1):
        fields = _extract_fields(item)
        fields["index"] = idx
        fields["provenance"] = []  # to be populated by linker
        citations.append(fields)
    # Optionally limit number of citations
    limit = options.get("limit")
    if isinstance(limit, int) and limit > 0:
        citations = citations[:limit]
    return citations

