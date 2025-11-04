from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Dict, Any, Iterable, List, Optional


_FLAG_MAP = {
    "ignorecase": re.IGNORECASE,
    "multiline": re.MULTILINE,
    "dotall": re.DOTALL,
    "verbose": re.VERBOSE,
}


def _compile_flags(flags: List[str] | None) -> int:
    value = 0
    for f in flags or []:
        if f.lower() in _FLAG_MAP:
            value |= _FLAG_MAP[f.lower()]
    return value


def _mask_middle(s: str, visible: int = 4) -> str:
    if s is None:
        return ""
    if len(s) <= visible * 2:
        return "*" * len(s)
    return s[:visible] + "*" * (len(s) - (visible * 2)) + s[-visible:]


@dataclass
class Match:
    start: int
    end: int
    line: int
    column: int
    snippet: str
    matched_text: str
    display_text: str


class _IndexMapper:
    def __init__(self, content: str):
        self.newlines = [-1]
        for i, ch in enumerate(content):
            if ch == "\n":
                self.newlines.append(i)
        self.length = len(content)

    def to_line_col(self, index: int) -> tuple[int, int]:
        # binary search over newline positions
        lo, hi = 0, len(self.newlines) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            if self.newlines[mid] < index:
                lo = mid + 1
            else:
                hi = mid - 1
        line = hi + 1  # 1-based line number
        col = index - self.newlines[hi]  # 1-based column
        return line, col

    def line_snippet(self, content: str, line: int, context: int = 0) -> str:
        # returns the given line text without trailing newline
        start = self.newlines[line - 1] + 1
        end = self.newlines[line] if line < len(self.newlines) else len(content)
        return content[start:end][:500]


@dataclass
class Policy:
    id: str
    type: str  # 'regex' or 'substring'
    pattern: str
    message: str
    severity: str = "medium"
    action: str = "warn"  # 'deny' or 'warn'
    flags: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    allowlist: List[str] = field(default_factory=list)  # regex patterns to ignore
    allow_inline_exemption: bool = True  # e.g., add line comment: POLICY-EXEMPT: <policy-id>
    redact: bool = False  # mask matched text in output
    max_match_display: int = 64

    _compiled: Optional[re.Pattern] = field(default=None, init=False, repr=False)
    _allowlist_compiled: List[re.Pattern] = field(default_factory=list, init=False, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Policy":
        required = ["id", "type", "pattern", "message"]
        for k in required:
            if k not in data:
                raise ValueError(f"policy missing required field '{k}'")
        p = cls(
            id=str(data["id"]),
            type=str(data["type"]).lower(),
            pattern=str(data["pattern"]),
            message=str(data["message"]),
            severity=str(data.get("severity", "medium")).lower(),
            action=str(data.get("action", "warn")).lower(),
            flags=[str(x).lower() for x in data.get("flags", [])],
            tags=[str(x) for x in data.get("tags", [])],
            allowlist=[str(x) for x in data.get("allowlist", [])],
            allow_inline_exemption=bool(data.get("allow_inline_exemption", True)),
            redact=bool(data.get("redact", False)),
            max_match_display=int(data.get("max_match_display", 64)),
        )
        p._build()
        return p

    def _build(self):
        if self.type not in ("regex", "substring"):
            raise ValueError(f"unsupported policy type: {self.type}")
        if self.type == "regex":
            self._compiled = re.compile(self.pattern, _compile_flags(self.flags))
        self._allowlist_compiled = [re.compile(p) for p in self.allowlist]
        if self.action not in ("deny", "warn"):
            raise ValueError(f"invalid action: {self.action}")

    def to_dict(self, include_pattern: bool = False) -> Dict[str, Any]:
        d = {
            "id": self.id,
            "type": self.type,
            "message": self.message,
            "severity": self.severity,
            "action": self.action,
            "flags": self.flags,
            "tags": self.tags,
            "allow_inline_exemption": self.allow_inline_exemption,
            "redact": self.redact,
        }
        if include_pattern:
            d["pattern"] = self.pattern
            if self.allowlist:
                d["allowlist"] = self.allowlist
        return d

    def _is_exempt(self, line_text: str) -> bool:
        # Inline exemption marker: POLICY-EXEMPT: <policy-id>
        if not self.allow_inline_exemption:
            return False
        marker = f"POLICY-EXEMPT: {self.id}"
        return marker in line_text

    def _is_allowlisted(self, text: str) -> bool:
        for p in self._allowlist_compiled:
            if p.search(text):
                return True
        return False

    def evaluate(self, content: str, metadata: Dict[str, Any] | None = None) -> Iterable[Match]:
        metadata = metadata or {}
        mapper = _IndexMapper(content)
        matches: List[Match] = []

        if self.type == "regex":
            assert self._compiled is not None
            for m in self._compiled.finditer(content):
                start, end = m.start(), m.end()
                line, col = mapper.to_line_col(start)
                line_text = mapper.line_snippet(content, line)
                if self._is_exempt(line_text):
                    continue
                matched_text = m.group(0)
                if self._is_allowlisted(matched_text):
                    continue
                display_text = self._format_match_display(matched_text)
                matches.append(Match(
                    start=start,
                    end=end,
                    line=line,
                    column=col,
                    snippet=line_text,
                    matched_text=matched_text,
                    display_text=display_text,
                ))
        else:  # substring
            query = self.pattern
            pos = 0
            while True:
                idx = content.find(query, pos)
                if idx == -1:
                    break
                start = idx
                end = idx + len(query)
                line, col = mapper.to_line_col(start)
                line_text = mapper.line_snippet(content, line)
                if self._is_exempt(line_text):
                    pos = end
                    continue
                if self._is_allowlisted(query):
                    pos = end
                    continue
                display_text = self._format_match_display(query)
                matches.append(Match(
                    start=start,
                    end=end,
                    line=line,
                    column=col,
                    snippet=line_text,
                    matched_text=query,
                    display_text=display_text,
                ))
                pos = end

        return matches

    def _format_match_display(self, text: str) -> str:
        t = text
        if self.redact:
            t = _mask_middle(text, visible=4)
        if len(t) > self.max_match_display:
            t = t[: self.max_match_display] + "..."
        return t

