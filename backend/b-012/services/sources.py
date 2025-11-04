import requests
import time
import datetime
import re
from typing import List, Dict, Tuple
import feedparser
from xml.etree import ElementTree as ET

USER_AGENT = 'OneClickLitReview/1.0 (+https://example.com; mailto:youremail@example.com)'

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})


def _clean_text(txt: str) -> str:
    if not txt:
        return ''
    # Remove HTML tags and normalize whitespace
    txt = re.sub(r'<[^>]+>', ' ', txt)
    txt = re.sub(r'\s+', ' ', txt).strip()
    return txt


def _dedup_papers(papers: List[Dict]) -> List[Dict]:
    seen = set()
    result = []
    for p in papers:
        key = (p.get('doi') or '').lower().strip()
        if not key:
            key = re.sub(r'\W+', '', (p.get('title') or '').lower())
        if key in seen:
            continue
        seen.add(key)
        result.append(p)
    return result


def search_crossref(query: str, from_year: int, max_results: int) -> List[Dict]:
    url = 'https://api.crossref.org/works'
    params = {
        'query': query,
        'filter': f'type:journal-article,from-pub-date:{from_year}-01-01',
        'sort': 'relevance',
        'order': 'desc',
        'rows': max_results
    }
    out = []
    try:
        r = session.get(url, params=params, timeout=20)
        r.raise_for_status()
        items = r.json().get('message', {}).get('items', [])
        for it in items:
            title = ' '.join(it.get('title') or [])
            authors = []
            for a in it.get('author', []) or []:
                given = a.get('given') or ''
                family = a.get('family') or ''
                name = (given + ' ' + family).strip()
                if name:
                    authors.append(name)
            year = None
            if it.get('published-print', {}).get('date-parts'):
                year = it['published-print']['date-parts'][0][0]
            elif it.get('published-online', {}).get('date-parts'):
                year = it['published-online']['date-parts'][0][0]
            elif it.get('issued', {}).get('date-parts'):
                year = it['issued']['date-parts'][0][0]
            doi = it.get('DOI')
            url_item = it.get('URL')
            abstract = _clean_text(it.get('abstract') or '')
            venue = (it.get('container-title') or [''])[0]
            citations = it.get('is-referenced-by-count') or 0
            out.append({
                'source': 'crossref',
                'title': title,
                'authors': authors,
                'year': year,
                'venue': venue,
                'url': url_item,
                'doi': doi,
                'abstract': abstract,
                'citations': citations,
                'pdf_url': None
            })
    except Exception:
        pass
    return out


def search_arxiv(query: str, from_year: int, max_results: int) -> List[Dict]:
    # arXiv atom feed, sorted by relevance
    url = 'https://export.arxiv.org/api/query'
    params = {
        'search_query': f'all:{query}',
        'start': 0,
        'max_results': max_results,
        'sortBy': 'relevance',
        'sortOrder': 'descending'
    }
    out = []
    try:
        feed = feedparser.parse(session.get(url, params=params, timeout=20).text)
        for entry in feed.entries:
            title = _clean_text(entry.title)
            abstract = _clean_text(getattr(entry, 'summary', ''))
            authors = [a.name for a in entry.authors] if hasattr(entry, 'authors') else []
            year = None
            if hasattr(entry, 'published') and entry.published:
                try:
                    year = int(entry.published[:4])
                except Exception:
                    year = None
            if year and year < from_year:
                continue
            links = {l.rel: l.href for l in entry.links}
            pdf_url = None
            for l in entry.links:
                if l.type == 'application/pdf':
                    pdf_url = l.href
            url_item = links.get('alternate') or getattr(entry, 'link', None)
            arxiv_id = None
            if hasattr(entry, 'id'):
                arxiv_id = entry.id.split('/')[-1]
            out.append({
                'source': 'arxiv',
                'title': title,
                'authors': authors,
                'year': year,
                'venue': 'arXiv',
                'url': url_item,
                'doi': None,
                'abstract': abstract,
                'citations': None,
                'pdf_url': pdf_url
            })
    except Exception:
        pass
    return out


def search_pubmed(query: str, from_year: int, max_results: int, email: str = '') -> List[Dict]:
    base = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils'
    params = {
        'db': 'pubmed',
        'retmode': 'json',
        'term': query,
        'retmax': max_results,
        'sort': 'relevance'
    }
    if email:
        params['email'] = email
    # Use mindate to limit years
    params['mindate'] = f'{from_year}/01/01'
    params['maxdate'] = f'{datetime.date.today().year}/12/31'

    out = []
    try:
        r = session.get(f'{base}/esearch.fcgi', params=params, timeout=20)
        r.raise_for_status()
        ids = r.json().get('esearchresult', {}).get('idlist', [])
        if not ids:
            return []
        fetch_params = {
            'db': 'pubmed',
            'id': ','.join(ids),
            'retmode': 'xml'
        }
        if email:
            fetch_params['email'] = email
        r2 = session.get(f'{base}/efetch.fcgi', params=fetch_params, timeout=30)
        r2.raise_for_status()
        root = ET.fromstring(r2.content)
        for article in root.findall('.//PubmedArticle'):
            art = article.find('.//Article')
            if art is None:
                continue
            title_el = art.find('ArticleTitle')
            title = _clean_text(''.join(title_el.itertext())) if title_el is not None else ''
            abstract = ''
            ab_el = art.find('Abstract')
            if ab_el is not None:
                parts = []
                for at in ab_el.findall('AbstractText'):
                    parts.append(''.join(at.itertext()))
                abstract = _clean_text(' '.join(parts))
            authors = []
            auth_list = art.find('AuthorList')
            if auth_list is not None:
                for person in auth_list.findall('Author'):
                    last = person.findtext('LastName') or ''
                    fore = person.findtext('ForeName') or ''
                    name = (fore + ' ' + last).strip()
                    if name:
                        authors.append(name)
            journal = art.find('Journal')
            venue = ''
            if journal is not None:
                venue = journal.findtext('Title') or ''
            year = None
            year_txt = article.findtext('.//PubDate/Year')
            if year_txt and year_txt.isdigit():
                year = int(year_txt)
            else:
                medline = article.findtext('.//DateCompleted/Year')
                if medline and medline.isdigit():
                    year = int(medline)
            url = None
            article_ids = article.findall('.//ArticleIdList/ArticleId')
            doi = None
            for aid in article_ids:
                if aid.attrib.get('IdType') == 'doi':
                    doi = aid.text
                if aid.attrib.get('IdType') == 'pubmed':
                    url = f'https://pubmed.ncbi.nlm.nih.gov/{aid.text}/'
            out.append({
                'source': 'pubmed',
                'title': title,
                'authors': authors,
                'year': year,
                'venue': venue,
                'url': url,
                'doi': doi,
                'abstract': abstract,
                'citations': None,
                'pdf_url': None
            })
    except Exception:
        pass
    return out


def search_all_sources(query: str, from_year: int, max_results: int, sources: List[str], pubmed_email: str = '') -> Tuple[List[Dict], List[str]]:
    sources = [s.lower() for s in sources]
    papers = []
    used = []

    if 'crossref' in sources:
        try:
            cr = search_crossref(query, from_year, max_results)
            if cr:
                used.append('crossref')
                papers.extend(cr)
        except Exception:
            pass
    if 'arxiv' in sources:
        try:
            ax = search_arxiv(query, from_year, max_results)
            if ax:
                used.append('arxiv')
                papers.extend(ax)
        except Exception:
            pass
    if 'pubmed' in sources:
        try:
            pm = search_pubmed(query, from_year, max_results, email=pubmed_email)
            if pm:
                used.append('pubmed')
                papers.extend(pm)
        except Exception:
            pass

    # Filter by from_year if year exists
    filtered = []
    for p in papers:
        y = p.get('year')
        if y is not None and isinstance(y, int):
            if y >= from_year:
                filtered.append(p)
        else:
            filtered.append(p)

    # Deduplicate
    deduped = _dedup_papers(filtered)

    return deduped, used

