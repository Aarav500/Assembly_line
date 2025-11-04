import time
import requests
from difflib import SequenceMatcher
from typing import List, Dict, Any, Optional

CROSSREF_BASE = "https://api.crossref.org"
TIMEOUT = 12


def _sim(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    a = a.lower().strip()
    b = b.lower().strip()
    return SequenceMatcher(None, a, b).ratio()


def _normalize_title(title: Optional[str]) -> Optional[str]:
    if not title:
        return None
    return " ".join(title.split()).strip(" .")


def _crossref_by_doi(doi: str) -> Optional[Dict[str, Any]]:
    url = f"{CROSSREF_BASE}/works/{requests.utils.quote(doi)}"
    r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "citation-extractor/1.0"})
    if r.status_code != 200:
        return None
    j = r.json()
    return j.get("message")


def _crossref_search_bibliographic(query: str, year: Optional[int] = None) -> Optional[Dict[str, Any]]:
    params = {
        "rows": 3,
        "query.bibliographic": query[:2048],
        "select": "DOI,URL,title,author,container-title,issued,type,publisher,volume,issue,page,score",
        "sort": "score",
        "order": "desc",
    }
    if year:
        params["filter"] = f"from-pub-date:{year}-01-01,until-pub-date:{year}-12-31"
    r = requests.get(f"{CROSSREF_BASE}/works", params=params, timeout=TIMEOUT, headers={"User-Agent": "citation-extractor/1.0"})
    if r.status_code != 200:
        return None
    items = r.json().get("message", {}).get("items", [])
    if not items:
        return None
    return items[0]


def _format_crossref_item(item: Dict[str, Any]) -> Dict[str, Any]:
    title = None
    if item.get("title"):
        title = item["title"][0]
    container = None
    if item.get("container-title"):
        container = item["container-title"][0]
    authors = []
    for a in item.get("author", [])[:10]:
        name = " ".join(filter(None, [a.get("given"), a.get("family")])) or a.get("name")
        if name:
            authors.append(name)
    year = None
    try:
        year = item.get("issued", {}).get("date-parts", [[None]])[0][0]
    except Exception:
        year = None
    doi = item.get("DOI")
    url = item.get("URL") or (f"https://doi.org/{doi}" if doi else None)
    return {
        "title": title,
        "authors": authors,
        "year": year,
        "venue": container,
        "publisher": item.get("publisher"),
        "type": item.get("type"),
        "volume": item.get("volume"),
        "issue": item.get("issue"),
        "page": item.get("page"),
        "doi": doi,
        "url": url,
        "source": "Crossref",
    }


def link_provenance(citations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    enriched = []
    for c in citations:
        raw = c.get("raw") or ""
        title_hint = _normalize_title(c.get("title"))
        best = None
        score = 0.0
        provenance_entries = []
        # 1) Direct DOI lookup if we have it
        doi = c.get("doi")
        if doi:
            try:
                item = _crossref_by_doi(doi)
                if item:
                    fr = _format_crossref_item(item)
                    t = _normalize_title(fr.get("title"))
                    s = max(_sim(raw, fr.get("title") or raw), _sim(title_hint or raw, t or raw))
                    best = fr
                    score = max(score, s)
                    provenance_entries.append({
                        "source": "Crossref",
                        "type": "doi-lookup",
                        "score": round(s, 4),
                        "id": fr.get("doi"),
                        "url": fr.get("url"),
                        "metadata": fr,
                    })
            except Exception:
                pass
        # 2) Bibliographic search if nothing or low score
        q = title_hint or raw
        if not best or score < 0.6:
            try:
                item = _crossref_search_bibliographic(q, c.get("year"))
                if item:
                    fr = _format_crossref_item(item)
                    t = _normalize_title(fr.get("title"))
                    s = max(_sim(raw, fr.get("title") or raw), _sim(title_hint or raw, t or raw))
                    if s > score:
                        best = fr
                        score = s
                    provenance_entries.append({
                        "source": "Crossref",
                        "type": "biblio-search",
                        "score": round(s, 4),
                        "id": fr.get("doi"),
                        "url": fr.get("url"),
                        "metadata": fr,
                    })
            except Exception:
                pass
        # Attach results
        c_out = dict(c)
        c_out.setdefault("provenance", [])
        c_out["provenance"].extend(provenance_entries)
        if best:
            c_out["linked"] = {
                "doi": best.get("doi"),
                "url": best.get("url"),
                "title": best.get("title"),
                "year": best.get("year"),
                "venue": best.get("venue"),
                "publisher": best.get("publisher"),
                "authors": best.get("authors"),
                "type": best.get("type"),
                "score": round(score, 4),
                "source": best.get("source"),
            }
        enriched.append(c_out)
        # Be nice to public APIs
        time.sleep(0.1)
    return enriched

