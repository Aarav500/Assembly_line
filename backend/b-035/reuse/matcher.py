import re
from dataclasses import dataclass
from typing import List

from .indexer import CorpusIndex


@dataclass
class MatchResult:
    artifact_id: str
    path: str
    title: str
    kind: str
    start_line: int
    end_line: int
    snippet: str
    score: float

    def to_dict(self):
        return {
            "artifact_id": self.artifact_id,
            "path": self.path,
            "title": self.title,
            "kind": self.kind,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "snippet": self.snippet,
            "score": round(self.score, 6),
        }


class IdeaMatcher:
    def __init__(self, index: CorpusIndex):
        self.index = index

    def split_idea(self, idea: str) -> List[str]:
        # Split by lines and sentence boundaries, keep meaningful parts
        parts = []
        # Normalize bullets to lines
        normalized = idea.replace("\r\n", "\n")
        for raw_line in normalized.split("\n"):
            line = raw_line.strip(" -\t")
            if not line:
                continue
            # further split by sentence boundaries
            sentences = re.split(r"(?<=[.!?;])\s+", line)
            for s in sentences:
                s = s.strip()
                if len(s) >= 5:
                    parts.append(s)
        # deduplicate while preserving order
        seen = set()
        uniq = []
        for p in parts:
            key = p.lower()
            if key not in seen:
                seen.add(key)
                uniq.append(p)
        return uniq or [idea]

    def match_part(self, part: str, top_k: int = 5) -> List[MatchResult]:
        scored = self.index.query(part, top_k=top_k)
        results: List[MatchResult] = []
        for art, score in scored:
            snippet = self._make_snippet(art.content, max_lines=12)
            results.append(MatchResult(
                artifact_id=art.id,
                path=art.path,
                title=art.title,
                kind=art.kind,
                start_line=art.start_line,
                end_line=art.end_line,
                snippet=snippet,
                score=score,
            ))
        return results

    def _make_snippet(self, content: str, max_lines: int = 12) -> str:
        lines = content.splitlines()
        if len(lines) <= max_lines:
            return content
        head = "\n".join(lines[: max_lines // 2])
        tail = "\n".join(lines[-(max_lines - max_lines // 2):])
        return head + "\n...\n" + tail

