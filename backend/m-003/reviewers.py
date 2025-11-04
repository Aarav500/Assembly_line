import os
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from codeowners import CodeOwners
from teams import TeamDirectory
from utils import to_posix_path, normalize_owner_id


@dataclass
class Reason:
    type: str  # 'codeowners' or 'git'
    files: List[str] = field(default_factory=list)
    patterns: List[str] = field(default_factory=list)  # for codeowners
    commits: int = 0  # for git


@dataclass
class Candidate:
    id: str  # normalized owner id (e.g., '@alice' or 'alice@example.com' or '@org/team')
    display: str  # original form to display
    kind: str  # 'user', 'team', or 'email'
    score: float = 0.0
    reasons: Dict[str, Reason] = field(default_factory=dict)

    def add_reason_file(self, reason_type: str, file: str, pattern: Optional[str] = None, commits: int = 0):
        r = self.reasons.get(reason_type)
        if not r:
            r = Reason(type=reason_type)
            self.reasons[reason_type] = r
        if file not in r.files:
            r.files.append(file)
        if pattern and pattern not in r.patterns:
            r.patterns.append(pattern)
        if commits:
            r.commits += commits


class SuggestionEngine:
    def __init__(self, repo_path: str, teams_path: Optional[str] = None):
        self.repo_path = os.path.abspath(repo_path)
        self.codeowners = CodeOwners.load(self.repo_path)
        self.teams = TeamDirectory.load(self.repo_path, teams_path)

    def suggest(
        self,
        changed_files: List[str],
        limit: int = 5,
        author: Optional[str] = None,
        include_teams: bool = False,
        use_git_history: bool = False,
    ) -> Dict:
        # Normalize inputs
        files = [to_posix_path(p).lstrip("./") for p in changed_files]
        author_norm = normalize_owner_id(author) if author else None

        candidates: Dict[str, Candidate] = {}

        # 1) Codeowners-based scoring
        for f in files:
            owners, rule = self.codeowners.match_owners(f)
            if not owners:
                continue
            specificity = self._pattern_specificity(rule.pattern)
            base_weight = 10 + specificity

            expanded = self.teams.expand_owners(owners)
            for owner in expanded:
                nid = normalize_owner_id(owner)
                disp = owner
                kind = owner_kind(owner)
                if nid not in candidates:
                    candidates[nid] = Candidate(id=nid, display=disp, kind=kind)
                candidates[nid].score += base_weight
                candidates[nid].add_reason_file("codeowners", f, pattern=rule.pattern)

        # 2) Optional git history-based scoring
        if use_git_history:
            for f in files:
                counts = git_author_counts(self.repo_path, f, max_commits=200)
                for email, c in counts.items():
                    nid = normalize_owner_id(email)
                    if nid not in candidates:
                        candidates[nid] = Candidate(id=nid, display=email, kind="email")
                    weight = min(c, 20) * 0.5  # cap influence of history
                    candidates[nid].score += weight
                    candidates[nid].add_reason_file("git", f, commits=c)

        # Filter out author if provided
        if author_norm:
            if author_norm in candidates:
                del candidates[author_norm]

        # Optionally exclude teams from final list unless requested
        filtered = [c for c in candidates.values() if include_teams or c.kind != "team"]

        # Sort by score desc, then by id
        filtered.sort(key=lambda c: (-c.score, c.id))

        # Limit results
        top = filtered[: max(1, int(limit))]

        # Build response
        suggestions = []
        for c in top:
            reasons_list = []
            for r in c.reasons.values():
                reasons_list.append({
                    "type": r.type,
                    "files": sorted(r.files),
                    "patterns": sorted(r.patterns) if r.patterns else [],
                    "commits": r.commits if r.commits else 0,
                })
            suggestions.append({
                "owner": c.display,
                "normalized_owner": c.id,
                "kind": c.kind,
                "score": round(c.score, 3),
                "reasons": reasons_list,
            })

        meta = {
            "repo_path": self.repo_path,
            "codeowners_path": self.codeowners.source_path,
            "files_considered": files,
            "used_git_history": bool(use_git_history),
            "include_teams": bool(include_teams),
        }

        return {"suggestions": suggestions, "meta": meta}

    @staticmethod
    def _pattern_specificity(pattern: str) -> int:
        # Higher for more specific (fewer wildcards)
        pat = pattern.strip("/")
        if not pat:
            return 0
        parts = [p for p in pat.split("/") if p]
        score = 0
        for p in parts:
            # component without wildcards increases specificity
            if "*" not in p and "?" not in p:
                score += 2
            else:
                # partial specificity: fewer wildcards => slightly higher
                wc = p.count("*") + p.count("?")
                score += max(0, 1 - wc)
        return score


def owner_kind(owner: str) -> str:
    o = owner.strip()
    if o.startswith("@") and "/" in o:
        return "team"
    if o.startswith("@"):
        return "user"
    if "@" in o:
        return "email"
    return "user"


def git_author_counts(repo_path: str, file_path: str, max_commits: int = 200) -> Dict[str, int]:
    # Returns a map of author emails to commit count for a given file
    try:
        # Use git log to get recent author emails touching this file
        cmd = [
            "git", "-C", repo_path, "log", f"-n{int(max_commits)}", "--format=%ae", "--", file_path
        ]
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
        lines = out.decode("utf-8", errors="ignore").splitlines()
        counts: Dict[str, int] = defaultdict(int)
        for line in lines:
            email = line.strip().lower()
            if email:
                counts[email] += 1
        return dict(counts)
    except Exception:
        return {}

