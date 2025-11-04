import os
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from utils import to_posix_path


CODEOWNERS_LOCATIONS = [
    "CODEOWNERS",
    os.path.join(".github", "CODEOWNERS"),
    os.path.join("docs", "CODEOWNERS"),
]


@dataclass
class CodeOwnerRule:
    pattern: str
    owners: List[str]
    line: int
    regex: re.Pattern


def _escape_regex_char(c: str) -> str:
    if c in ".^$+{}[]()|\\":
        return "\\" + c
    return c


def codeowners_pattern_to_regex(pattern: str) -> re.Pattern:
    # Approximation of GitHub CODEOWNERS pattern semantics
    pat = pattern.strip()
    anchored = pat.startswith("/")
    if anchored:
        pat = pat[1:]

    dir_only = pat.endswith("/")
    if dir_only:
        pat = pat[:-1]

    i = 0
    regex = ""
    while i < len(pat):
        two = pat[i:i+2]
        if two == "**":
            regex += ".*"
            i += 2
            continue
        ch = pat[i]
        if ch == "*":
            regex += "[^/]*"
        elif ch == "?":
            regex += "[^/]"
        else:
            regex += _escape_regex_char(ch)
        i += 1

    if dir_only:
        regex = f"{regex}(?:/.*)?"

    if anchored:
        full = f"^{regex}$"
    else:
        # Match from any directory depth
        full = f"(^|.*/){regex}$"

    return re.compile(full)


class CodeOwners:
    def __init__(self, rules: List[CodeOwnerRule], source_path: Optional[str]):
        self.rules = rules
        self.source_path = source_path

    @staticmethod
    def find_file(repo_path: str) -> Optional[str]:
        for rel in CODEOWNERS_LOCATIONS:
            candidate = os.path.join(repo_path, rel)
            if os.path.isfile(candidate):
                return candidate
        return None

    @staticmethod
    def load(repo_path: str) -> "CodeOwners":
        path = CodeOwners.find_file(repo_path)
        if not path:
            return CodeOwners([], None)
        rules: List[CodeOwnerRule] = []
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for idx, line in enumerate(f, start=1):
                raw = line.strip()
                if not raw or raw.startswith("#"):
                    continue
                # Split on spaces/tabs while supporting patterns with escaped spaces
                parts = _split_codeowners_line(raw)
                if not parts:
                    continue
                pattern = parts[0]
                owners = parts[1:]
                if not owners:
                    continue
                regex = codeowners_pattern_to_regex(pattern)
                rules.append(CodeOwnerRule(pattern=pattern, owners=owners, line=idx, regex=regex))
        return CodeOwners(rules, path)

    def match_owners(self, file_path: str) -> Tuple[List[str], Optional[CodeOwnerRule]]:
        if not self.rules:
            return [], None
        p = to_posix_path(file_path).lstrip("./")
        matched_rule: Optional[CodeOwnerRule] = None
        for rule in self.rules:
            if rule.regex.search(p):
                matched_rule = rule
        if matched_rule is None:
            return [], None
        return matched_rule.owners, matched_rule


def _split_codeowners_line(line: str) -> List[str]:
    # Split by whitespace, but allow escaped spaces in patterns
    parts: List[str] = []
    buf = []
    i = 0
    in_escape = False
    while i < len(line):
        ch = line[i]
        if in_escape:
            buf.append(ch)
            in_escape = False
            i += 1
            continue
        if ch == "\\":
            in_escape = True
            i += 1
            continue
        if ch.isspace():
            if buf:
                parts.append("".join(buf))
                buf = []
            # skip contiguous whitespace
            while i < len(line) and line[i].isspace():
                i += 1
            continue
        buf.append(ch)
        i += 1
    if buf:
        parts.append("".join(buf))
    return parts

