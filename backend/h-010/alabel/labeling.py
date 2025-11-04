import re
from collections import Counter
from typing import List, Dict, Optional

ABSTAIN = None

class BaseLF:
    def __init__(self, name: str, on: str = 'text', params: Optional[dict] = None):
        self.name = name
        self.on = on or 'text'
        self.params = params or {}

    def apply(self, row: dict) -> Optional[str]:
        raise NotImplementedError

    @staticmethod
    def from_config(cfg: dict):
        lf_type = cfg.get('type')
        cls = LF_REGISTRY.get(lf_type)
        if not cls:
            raise ValueError(f"Unknown labeling function type: {lf_type}")
        return cls(name=cfg.get('name', lf_type), on=cfg.get('on', 'text'), params=cfg.get('params', {}))

class KeywordLF(BaseLF):
    # params: {label: str, keywords: [str], case_sensitive: bool=False, whole_word: bool=False}
    def apply(self, row: dict) -> Optional[str]:
        text = (row.get(self.on) or '')
        label = self.params.get('label')
        kws = self.params.get('keywords', [])
        if not label or not kws:
            return ABSTAIN
        case_sensitive = bool(self.params.get('case_sensitive', False))
        whole_word = bool(self.params.get('whole_word', False))
        haystack = text if case_sensitive else text.lower()
        if whole_word:
            tokens = set(re.findall(r"\w+", haystack))
            for kw in kws:
                k = kw if case_sensitive else kw.lower()
                if k in tokens:
                    return label
        else:
            for kw in kws:
                k = kw if case_sensitive else kw.lower()
                if k in haystack:
                    return label
        return ABSTAIN

class RegexLF(BaseLF):
    # params: patterns: [{label: str, pattern: str, flags: str|null}]
    def __init__(self, name: str, on: str = 'text', params: Optional[dict] = None):
        super().__init__(name, on, params)
        self._compiled = []
        for p in self.params.get('patterns', []):
            flags = 0
            flag_str = p.get('flags') or ''
            if 'i' in flag_str:
                flags |= re.IGNORECASE
            if 'm' in flag_str:
                flags |= re.MULTILINE
            if 's' in flag_str:
                flags |= re.DOTALL
            try:
                self._compiled.append((p.get('label'), re.compile(p.get('pattern', ''), flags)))
            except re.error:
                # skip invalid regex
                continue

    def apply(self, row: dict) -> Optional[str]:
        text = (row.get(self.on) or '')
        for label, pat in self._compiled:
            if label and pat and pat.search(text):
                return label
        return ABSTAIN

class ContainsAnyLF(BaseLF):
    # params: {label_map: {label: [keywords]}, case_sensitive: bool=False}
    def apply(self, row: dict) -> Optional[str]:
        text = (row.get(self.on) or '')
        case_sensitive = bool(self.params.get('case_sensitive', False))
        haystack = text if case_sensitive else text.lower()
        label_map: Dict[str, List[str]] = self.params.get('label_map', {}) or {}
        for label, kws in label_map.items():
            for kw in (kws or []):
                k = kw if case_sensitive else kw.lower()
                if k and k in haystack:
                    return label
        return ABSTAIN

class SentimentHeuristicLF(BaseLF):
    # params: {positive: [str], negative: [str], neutral_label: str|null}
    DEFAULT_POS = [
        'good','great','love','excellent','amazing','awesome','fantastic','nice','happy','like','wonderful','best'
    ]
    DEFAULT_NEG = [
        'bad','terrible','awful','hate','worst','poor','horrible','sad','angry','dislike','disappoint','bug','issue'
    ]
    def apply(self, row: dict) -> Optional[str]:
        text = (row.get(self.on) or '').lower()
        pos_words = set(self.params.get('positive') or self.DEFAULT_POS)
        neg_words = set(self.params.get('negative') or self.DEFAULT_NEG)
        pos = sum(w in text for w in pos_words)
        neg = sum(w in text for w in neg_words)
        if pos == 0 and neg == 0:
            # abstain unless neutral specified
            neutral = self.params.get('neutral_label')
            return neutral if neutral else ABSTAIN
        return 'positive' if pos > neg else ('negative' if neg > pos else (self.params.get('neutral_label') or ABSTAIN))

LF_REGISTRY = {
    'keyword': KeywordLF,
    'regex': RegexLF,
    'contains_any': ContainsAnyLF,
    'sentiment': SentimentHeuristicLF,
}

class MajorityVoteAggregator:
    def __init__(self, label_set: List[str], abstain_label: Optional[str] = None, tie_break: str = 'abstain', min_votes: int = 1):
        self.label_set = set(label_set or [])
        self.abstain_label = abstain_label
        self.tie_break = tie_break
        self.min_votes = max(0, int(min_votes))

    def aggregate(self, votes: List[Optional[str]]) -> Optional[str]:
        filtered = [v for v in votes if v is not None and v in self.label_set]
        if len(filtered) < self.min_votes or not filtered:
            return self._abstain()
        counts = Counter(filtered)
        most_common = counts.most_common()
        if len(most_common) == 0:
            return self._abstain()
        if len(most_common) == 1:
            return most_common[0][0]
        top_count = most_common[0][1]
        top_labels = [label for label, c in most_common if c == top_count]
        if len(top_labels) == 1:
            return top_labels[0]
        # tie
        if self.tie_break == 'first':
            return top_labels[0]
        elif self.tie_break == 'random':
            import random
            return random.choice(top_labels)
        else:
            return self._abstain()

    def _abstain(self) -> Optional[str]:
        return self.abstain_label if self.abstain_label is not None else ABSTAIN


def build_lfs(lf_configs: List[dict]) -> List[BaseLF]:
    return [BaseLF.from_config(cfg) for cfg in (lf_configs or [])]


def build_aggregator(agg_cfg: dict, label_set: List[str]):
    agg_type = (agg_cfg or {}).get('type', 'majority_vote')
    if agg_type != 'majority_vote':
        raise ValueError(f"Unsupported aggregator: {agg_type}")
    return MajorityVoteAggregator(
        label_set=label_set,
        abstain_label=agg_cfg.get('abstain_label', None),
        tie_break=agg_cfg.get('tie_break', 'abstain'),
        min_votes=agg_cfg.get('min_votes', 1),
    )

