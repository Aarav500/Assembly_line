import math
import re
from typing import Dict, List, Tuple
from ..models import db, Document, Term, Taxonomy, DocumentTerm
from ..utils.text import normalize_text, tokenize


class Categorizer:
    def __init__(self, default_threshold: float = 1.0):
        self.default_threshold = default_threshold

    def _compile_keyword(self, raw) -> Tuple[re.Pattern, float, str]:
        # raw can be string or {pattern, weight}
        weight = 1.0
        if isinstance(raw, dict):
            pattern = raw.get('pattern', '').strip()
            weight = float(raw.get('weight', 1.0))
        else:
            pattern = str(raw).strip()
        if not pattern:
            pattern = "__invalid__"
        if pattern.startswith('re:'):
            regex = re.compile(pattern[3:], flags=re.IGNORECASE)
            key = pattern
        else:
            escaped = re.escape(pattern)
            # word boundaries, allow spaces in phrases
            regex = re.compile(rf"\b{escaped}\b", flags=re.IGNORECASE)
            key = pattern
        return regex, weight, key

    def _term_threshold(self, term: Term, taxonomy_map: Dict[int, Taxonomy]) -> float:
        tax = taxonomy_map.get(term.taxonomy_id)
        return float(term.threshold or (tax.default_threshold if tax and tax.default_threshold is not None else self.default_threshold))

    def _term_weight(self, term: Term) -> float:
        return float(term.weight if term.weight is not None else 1.0)

    def categorize_text(self, text: str, terms: List[Term], taxonomy_map: Dict[int, Taxonomy], max_terms: int = 100) -> List[Dict]:
        # Normalize once
        normalized = normalize_text(text)
        tokens = tokenize(normalized)
        norm_factor = max(1.0, math.log(len(tokens) + 1, 10))

        results = []
        for term in terms:
            raw_keywords = term.keywords or []
            compiled = [self._compile_keyword(k) for k in raw_keywords]
            raw_score = 0.0
            matched_keys = []
            for regex, kw_weight, key in compiled:
                matches = regex.findall(normalized)
                count = len(matches)
                if count > 0:
                    matched_keys.append({'pattern': key, 'count': count, 'weight': kw_weight})
                    raw_score += count * kw_weight
            if raw_score <= 0:
                continue
            score = (raw_score * self._term_weight(term)) / norm_factor
            threshold = self._term_threshold(term, taxonomy_map)
            if score >= threshold:
                results.append({
                    'term': term,
                    'score': float(score),
                    'matched_keywords': matched_keys,
                })

        # Sort by score desc and limit
        results.sort(key=lambda r: r['score'], reverse=True)
        if max_terms:
            results = results[:max_terms]
        return results

    def categorize_document(self, document: Document, taxonomy_ids: List[int] = None, min_score: float = None, replace: bool = True):
        # Fetch terms and taxonomies
        query = Term.query
        if taxonomy_ids:
            query = query.filter(Term.taxonomy_id.in_(taxonomy_ids))
        terms = query.all()
        taxonomies = Taxonomy.query.all()
        taxonomy_map = {t.id: t for t in taxonomies}

        assignments = self.categorize_text(document.content, terms, taxonomy_map)
        # Optional filter by min_score
        if min_score is not None:
            assignments = [a for a in assignments if a['score'] >= float(min_score)]

        if replace:
            DocumentTerm.query.filter_by(document_id=document.id).delete()

        created = []
        for a in assignments:
            link = DocumentTerm(
                document_id=document.id,
                term_id=a['term'].id,
                score=a['score'],
                matched_keywords=a['matched_keywords'],
            )
            db.session.add(link)
            created.append(link)
        db.session.commit()

        return created

