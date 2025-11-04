import random
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from .citation_manager import CitationManager, Reference


@dataclass
class SectionSpec:
    title: str
    min_sentences: int
    max_sentences: int


DEFAULT_SECTIONS: List[SectionSpec] = [
    SectionSpec('Introduction', 5, 9),
    SectionSpec('Background and Related Work', 6, 10),
    SectionSpec('Methods', 5, 9),
    SectionSpec('Experiments', 4, 8),
    SectionSpec('Results', 4, 8),
    SectionSpec('Discussion', 4, 8),
    SectionSpec('Conclusion', 3, 6),
]


def parse_bibtex_entries(text: str) -> List[Dict]:
    entries = []
    if not text:
        return entries
    # Very minimal parser for common fields
    pattern = re.compile(r"@(?P<type>\w+)\s*\{\s*(?P<key>[^,]+),(?P<body>.*?)\}\s*", re.DOTALL)
    fields_pat = re.compile(r"(\w+)\s*=\s*[\"\{]([^\"\}]*)[\"\}]", re.DOTALL)
    for m in pattern.finditer(text):
        body = m.group('body')
        fields = dict((k.lower(), v.strip().replace('\n', ' ')) for k, v in fields_pat.findall(body))
        entries.append({
            'key': m.group('key').strip(),
            'title': fields.get('title') or 'Untitled',
            'author': fields.get('author') or 'Anonymous',
            'year': fields.get('year') or 'n.d.',
            'venue': fields.get('journal') or fields.get('booktitle') or fields.get('publisher') or 'n.p.',
        })
    return entries


def parse_plain_references(text: str) -> List[Dict]:
    refs = []
    if not text:
        return refs
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        # Support formats like: Author - Title - Venue - Year OR Author; Title; Venue; Year
        sep = ';' if ';' in line else '-'
        parts = [p.strip() for p in line.split(sep)]
        while len(parts) < 4:
            parts.append('')
        author, title, venue, year = parts[:4]
        refs.append({
            'key': re.sub(r'\W+', '', (author.split(',')[0] + year) or 'refkey'),
            'title': title or 'Untitled',
            'author': author or 'Anonymous',
            'year': year or 'n.d.',
            'venue': venue or 'n.p.',
        })
    return refs


def seed_references_from_text(text: str) -> List[Dict]:
    text = text or ''
    if '@' in text:
        entries = parse_bibtex_entries(text)
        if entries:
            return entries
    return parse_plain_references(text)


def fabricate_references(topic: str, n: int) -> List[Dict]:
    # Generate plausible dummy references
    authors_pool = [
        'Smith, J.', 'Lee, K.', 'Garcia, M.', 'Kumar, R.', 'Chen, L.', 'Brown, A.', 'Nguyen, T.',
        'Davis, P.', 'Martinez, S.', 'Wilson, E.', 'Taylor, B.', 'Anderson, C.', 'Thomas, R.'
    ]
    venues = [
        'Journal of ' + w for w in ['Computational Studies', 'Applied Science', 'Data Research', 'Systems']
    ] + [
        'Proceedings of the International Conference on ' + w for w in ['Machine Learning', 'Data Mining', 'Systems Engineering', 'Human-Computer Interaction']
    ]
    words = [w for w in re.sub(r'\W+', ' ', topic).split() if w]
    base_title = ' '.join([w.capitalize() for w in words[:5]]) or 'Research Directions'

    refs = []
    used_keys = set()
    year_base = random.randint(2012, 2024)
    for i in range(n):
        a1 = random.choice(authors_pool)
        a2 = random.choice(authors_pool)
        authors = f"{a1} and {a2}" if a2 != a1 else a1
        year = str(year_base - random.randint(0, 12))
        title_variants = [
            f"On {base_title}",
            f"A Study of {base_title}",
            f"Advances in {base_title}",
            f"{base_title}: Methods and Applications",
            f"Evaluating {base_title}"
        ]
        title = random.choice(title_variants)
        venue = random.choice(venues)
        key = re.sub(r'\W+', '', (authors.split(',')[0] + year))
        if key in used_keys:
            key = f"{key}{i}"
        used_keys.add(key)
        refs.append({'key': key, 'title': title, 'author': authors, 'year': year, 'venue': venue})
    return refs


def build_citation_manager(topic: str, references_text: str, n_needed: int, style: str) -> CitationManager:
    provided = seed_references_from_text(references_text)
    if len(provided) < max(3, n_needed // 2):
        provided.extend(fabricate_references(topic, max(0, n_needed - len(provided))))
    # Deduplicate by (author+title+year)
    seen = set()
    refs: List[Reference] = []
    idx = 1
    for r in provided:
        sig = (r.get('author', ''), r.get('title', ''), r.get('year', ''))
        if sig in seen:
            continue
        seen.add(sig)
        refs.append(Reference(
            id=idx,
            key=r.get('key') or f"ref{idx}",
            title=r.get('title') or 'Untitled',
            authors=r.get('author') or 'Anonymous',
            year=r.get('year') or 'n.d.',
            venue=r.get('venue') or 'n.p.',
        ))
        idx += 1
    return CitationManager(refs, style=style)


SENTENCE_TEMPLATES = [
    "This work investigates TOPIC, emphasizing ASPECT and potential applications CITS.",
    "Recent studies have highlighted the importance of KEYWORD in the context of TOPIC CITS.",
    "We propose a method that integrates KEYWORD with established approaches to improve OUTCOME CITS.",
    "A critical challenge for TOPIC lies in LIMITATION, which we address through our framework CITS.",
    "The methodology leverages DATA and MODEL components to optimize PERFORMANCE CITS.",
    "Prior art provides strong baselines; however, our approach yields consistent gains across SETTINGS CITS.",
    "We evaluate our method on multiple benchmarks and report comprehensive analyses CITS.",
    "The results suggest practical implications for DEPLOYMENT and future research CITS.",
    "In contrast to existing techniques, our design reduces complexity while maintaining accuracy CITS.",
    "We discuss threats to validity and outline replication resources for reproducibility CITS."
]


def fill_template(tpl: str, topic: str, keywords: List[str], cm: CitationManager) -> str:
    replacements = {
        'TOPIC': topic,
        'ASPECT': random.choice(['scalability', 'robustness', 'interpretability', 'efficiency', 'generalization']),
        'KEYWORD': random.choice(keywords) if keywords else topic.split()[0],
        'OUTCOME': random.choice(['accuracy', 'throughput', 'efficacy', 'stability', 'fairness']),
        'LIMITATION': random.choice(['data scarcity', 'distribution shift', 'computational cost', 'label noise', 'privacy constraints']),
        'DATA': random.choice(['synthetic data', 'real-world datasets', 'multimodal inputs', 'time-series signals']),
        'MODEL': random.choice(['probabilistic models', 'neural networks', 'graph methods', 'optimization routines']),
        'PERFORMANCE': random.choice(['overall performance', 'sample efficiency', 'latency', 'memory footprint']),
        'SETTINGS': random.choice(['tasks', 'domains', 'scenarios', 'datasets']),
        'DEPLOYMENT': random.choice(['industrial settings', 'edge devices', 'cloud platforms', 'scientific workflows']),
    }
    for k, v in replacements.items():
        tpl = tpl.replace(k, v)
    # Insert citations
    cit_count = 0 if random.random() < 0.3 else 1
    if random.random() > 0.7:
        cit_count += 1
    ids = cm.get_random_ids(cit_count)
    citation = (' ' + cm.inline(ids)) if ids else ''
    tpl = tpl.replace('CITS', citation)
    return tpl


def make_paragraph(topic: str, keywords: List[str], cm: CitationManager, sentences: int) -> str:
    sents = []
    for _ in range(sentences):
        tpl = random.choice(SENTENCE_TEMPLATES)
        sents.append(fill_template(tpl, topic, keywords, cm))
    return ' ' + ' '.join(sents)


def length_to_counts(length: str) -> Tuple[int, int, int]:
    if length == 'short':
        return (4, 2, 8)  # abstract sentences, min/max per section
    if length == 'long':
        return (7, 6, 12)
    return (5, 4, 10)


def summarize_abstract(topic: str, keywords: List[str], cm: CitationManager, sentences: int) -> str:
    # Simple abstract assembly
    parts = [
        f"We present a study on {topic} addressing core challenges and opportunities.",
        f"Our contributions include a principled methodology and an extensive evaluation.",
        f"Empirical results demonstrate improvements over strong baselines {cm.inline(cm.get_random_ids(1))}.",
        f"We discuss broader impacts and outline directions for future work.",
        f"The findings provide actionable guidance for practitioners and researchers alike."
    ]
    random.shuffle(parts)
    return ' '.join(parts[:sentences])


def generate_paper(topic: str,
                   title: Optional[str] = None,
                   authors: str = 'Automated Researcher',
                   length: str = 'medium',
                   keywords: str = '',
                   references_text: str = '',
                   citation_style: str = 'numeric') -> Dict:
    random.seed()
    kw_list = [k.strip() for k in re.split(r",|;|\n", keywords or '') if k.strip()]

    abstract_sents, min_sec, max_sec = length_to_counts(length)
    # Prepare citations
    cm = build_citation_manager(topic, references_text, n_needed=12, style=citation_style)

    # Title
    final_title = title or f"A Structured Study of {topic}" if topic else 'Untitled'

    # Abstract
    abstract = summarize_abstract(topic, kw_list, cm, sentences=abstract_sents)

    # Sections
    sections = []
    for spec in DEFAULT_SECTIONS:
        num = random.randint(min_sec, max_sec)
        content = make_paragraph(topic, kw_list, cm, sentences=num)
        sections.append({'title': spec.title, 'content': content})

    # Convert references to serializable dicts
    references = []
    for r in cm.all():
        references.append({
            'id': r.id,
            'key': r.key,
            'title': r.title,
            'authors': r.authors,
            'year': r.year,
            'venue': r.venue,
        })

    # Assemble paper
    paper = {
        'title': final_title,
        'topic': topic,
        'authors': authors,
        'abstract': abstract,
        'sections': sections,
        'references': references,
        'citation_style': citation_style,
    }

    return paper

