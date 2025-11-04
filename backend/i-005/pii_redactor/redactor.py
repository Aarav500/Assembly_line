import re
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple


@dataclass
class PiiMatch:
    start: int
    end: int
    value: str
    kind: str


class PiiRedactor:
    def __init__(self):
        # Compile regex patterns
        self.patterns = {
            'CREDIT_CARD': re.compile(r'(?:(?<=\D)|^)\b(?:\d[ -]*?){12,19}\b(?=\D|$)')
            , 'SSN': re.compile(r'(?:(?<=\D)|^)\b\d{3}-?\d{2}-?\d{4}\b(?=\D|$)')
            , 'EMAIL': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')
            , 'PHONE': re.compile(r'(?:(?<=\D)|^)(?:\+1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?|\d{3}[-.\s]?)\d{3}[-.\s]?\d{4}(?=\D|$)')
            , 'IPV4': re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
            , 'IPV6': re.compile(r'\b(?:[A-Fa-f0-9]{1,4}:){7}[A-Fa-f0-9]{1,4}\b|\b(?:(?:[A-Fa-f0-9]{1,4}:){1,7}:|:(?::[A-Fa-f0-9]{1,4}){1,7})\b')
            , 'DATE': re.compile(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b')
        }
        # Priority for resolving overlaps (higher first)
        self.priority = ['CREDIT_CARD', 'SSN', 'EMAIL', 'PHONE', 'IPV6', 'IPV4', 'DATE']

    def _luhn_check(self, s: str) -> bool:
        digits = [int(ch) for ch in s if ch.isdigit()]
        if len(digits) < 12:
            return False
        checksum = 0
        parity = (len(digits) - 2) % 2
        for i, d in enumerate(digits[::-1]):
            if i % 2 == 1:
                d *= 2
                if d > 9:
                    d -= 9
            checksum += d
        return checksum % 10 == 0

    def _valid_ipv4(self, s: str) -> bool:
        parts = s.split('.')
        if len(parts) != 4:
            return False
        try:
            return all(0 <= int(p) <= 255 for p in parts)
        except ValueError:
            return False

    def _collect_matches(self, text: str) -> List[PiiMatch]:
        matches: List[PiiMatch] = []
        for kind, pattern in self.patterns.items():
            for m in pattern.finditer(text):
                val = m.group(0)
                if kind == 'CREDIT_CARD':
                    digits = ''.join(ch for ch in val if ch.isdigit())
                    if not self._luhn_check(digits):
                        continue
                if kind == 'IPV4' and not self._valid_ipv4(val):
                    continue
                matches.append(PiiMatch(start=m.start(), end=m.end(), value=val, kind=kind))
        # Resolve overlaps by priority and longest span
        matches.sort(key=lambda x: (x.start, -(x.end - x.start)))
        accepted: List[PiiMatch] = []
        def pri(k: str) -> int:
            return self.priority.index(k) if k in self.priority else len(self.priority)
        for m in matches:
            overlap = False
            for a in accepted:
                if not (m.end <= a.start or m.start >= a.end):
                    # overlap detected, keep higher priority or longer span
                    if pri(m.kind) < pri(a.kind) or ((pri(m.kind) == pri(a.kind)) and (m.end - m.start) > (a.end - a.start)):
                        # replace a with m
                        accepted.remove(a)
                        accepted.append(m)
                    overlap = True
                    break
            if not overlap:
                accepted.append(m)
        accepted.sort(key=lambda x: x.start)
        return accepted

    def _replacement_for(self, kind: str, value: str) -> str:
        if kind in ('CREDIT_CARD', 'PHONE', 'SSN'):
            digits = ''.join(ch for ch in value if ch.isdigit())
            tail = digits[-4:] if len(digits) >= 4 else digits
            return f"[REDACTED:{kind}:***{tail}]"
        return f"[REDACTED:{kind}]"

    def redact(self, text: str) -> Dict[str, Any]:
        matches = self._collect_matches(text)
        if not matches:
            return {
                'redacted_text': text,
                'total_matches': 0,
                'counts_by_type': {},
                'matches': [],
                'sample_matches': []
            }
        out = []
        idx = 0
        counts: Dict[str, int] = {}
        meta_matches: List[Dict[str, Any]] = []
        for m in matches:
            out.append(text[idx:m.start])
            replacement = self._replacement_for(m.kind, m.value)
            out.append(replacement)
            counts[m.kind] = counts.get(m.kind, 0) + 1
            meta_matches.append({
                'kind': m.kind,
                'start': m.start,
                'end': m.end,
                'original_sample': m.value[:8] + ('...' if len(m.value) > 8 else ''),
                'replacement': replacement
            })
            idx = m.end
        out.append(text[idx:])
        redacted_text = ''.join(out)
        # Provide up to 10 sample matches
        sample = meta_matches[:10]
        return {
            'redacted_text': redacted_text,
            'total_matches': sum(counts.values()),
            'counts_by_type': counts,
            'matches': meta_matches,
            'sample_matches': sample
        }

    def redact_string(self, text: str) -> str:
        return self.redact(text)['redacted_text']

