import os
import re
from collections import Counter, defaultdict
from typing import List, Optional, Dict, Any

CATEGORY_PATTERNS = {
    "tests": [
        re.compile(r"(^|/)tests?(/|$)"),
        re.compile(r"(^|/)test_.*\.py$"),
        re.compile(r"_test\.py$")
    ],
    "docs": [
        re.compile(r"(^|/)docs(/|$)"),
        re.compile(r"\.md$"),
        re.compile(r"\.rst$"),
        re.compile(r"\.adoc$"),
        re.compile(r"\.txt$")
    ],
    "config": [
        re.compile(r"\.ya?ml$"),
        re.compile(r"\.json$"),
        re.compile(r"\.toml$"),
        re.compile(r"\.ini$"),
        re.compile(r"\.cfg$")
    ],
    "templates": [
        re.compile(r"\.jinja2?$"),
        re.compile(r"\.tpl$"),
        re.compile(r"\.html?$")
    ],
    "scripts": [
        re.compile(r"\.sh$"),
        re.compile(r"\.bash$"),
        re.compile(r"\.ps1$"),
        re.compile(r"\.cmd$"),
        re.compile(r"\.bat$")
    ],
    "data": [
        re.compile(r"\.csv$"),
        re.compile(r"\.tsv$"),
        re.compile(r"\.parquet$"),
        re.compile(r"\.sql$")
    ],
    "code": [
        re.compile(r"\.py$"),
        re.compile(r"\.js$"),
        re.compile(r"\.ts$"),
        re.compile(r"\.go$"),
        re.compile(r"\.java$"),
        re.compile(r"\.rb$"),
        re.compile(r"\.php$"),
        re.compile(r"\.(c|cc|cpp|cs)$")
    ],
}

STATUS_MAP = {
    'A': 'added',
    'M': 'modified',
    'D': 'deleted',
    'R': 'renamed',
    'C': 'copied',
    'T': 'typechanged',
    'U': 'unmerged',
}

def _first_meaningful_line(message: Optional[str]) -> Optional[str]:
    if not message:
        return None
    for line in message.splitlines():
        if not line.strip():
            # stop at the first blank if nothing found yet
            continue
        if line.lstrip().startswith('#'):
            continue
        # stop at trailers? We want the subject: first non-comment line
        return line.strip()
    return None

def _categorize(path: str) -> str:
    for cat, patterns in CATEGORY_PATTERNS.items():
        for pat in patterns:
            if pat.search(path):
                return cat
    return "other"

_def_prefix_re = re.compile(r"^(feat|fix|docs|refactor|chore|test|perf|build|ci|style)(\([^)]+\))?:\s*", re.I)

def _intent_from_subject(subject: Optional[str]) -> Optional[str]:
    if not subject:
        return None
    s = subject.strip()
    s = _def_prefix_re.sub("", s)
    s = s.rstrip('.').strip()
    if not s:
        return None
    # Capitalize first letter
    return s[0].upper() + s[1:]


def _format_categories(counts: Counter) -> Optional[str]:
    if not counts:
        return None
    # remove other if there are other categories present
    counts = counts.copy()
    if len(counts) > 1 and 'other' in counts:
        del counts['other']
    if not counts:
        return None
    top = counts.most_common(2)
    cats = [name for name, _ in top]
    if not cats:
        return None
    if len(cats) == 1:
        return cats[0]
    return f"{cats[0]} and {cats[1]}"


def generate_explanation(message: Optional[str] = None, files: Optional[List[Dict[str, Any]]] = None, diff: Optional[str] = None) -> str:
    """
    Produce a one-sentence rationale for the change based on commit message and file-level stats.
    files: list of {path: str, status: str, additions: int, deletions: int, old_path?: str}
    """
    subject = _first_meaningful_line(message)
    intent = _intent_from_subject(subject)

    total_add, total_del = 0, 0
    status_counts = Counter()
    category_counts = Counter()
    file_count = 0

    if files:
        for f in files:
            path = f.get('path') or ''
            status = (f.get('status') or '').upper()[:1]
            additions = int(f.get('additions') or 0)
            deletions = int(f.get('deletions') or 0)
            total_add += max(0, additions)
            total_del += max(0, deletions)
            file_count += 1
            status_counts[STATUS_MAP.get(status, 'modified')] += 1
            cat = _categorize(path)
            category_counts[cat] += 1

    # Fallbacks
    if file_count == 0 and diff:
        # crude estimation if only diff text is available
        add = len([1 for line in diff.splitlines() if line.startswith('+') and not line.startswith('+++')])
        rem = len([1 for line in diff.splitlines() if line.startswith('-') and not line.startswith('---')])
        total_add, total_del = add, rem
        file_count = 1 if (add or rem) else 0

    # derive intent if missing
    if not intent:
        if status_counts['added'] > max(status_counts['modified'], status_counts['deleted']):
            intent = "Introduce new functionality"
        elif category_counts['tests']:
            intent = "Improve test coverage"
        elif category_counts['docs']:
            intent = "Update documentation"
        else:
            intent = "Update codebase"

    scope_bits = []
    if file_count:
        scope_bits.append(f"across {file_count} file{'s' if file_count != 1 else ''}")
    scope_bits.append(f"+{total_add}/-{total_del}")

    if status_counts['renamed']:
        scope_bits.append(f"including {status_counts['renamed']} rename{'s' if status_counts['renamed'] != 1 else ''}")

    cats = _format_categories(category_counts)
    if cats:
        scope_bits.append(f"mainly in {cats}")

    scope = ", ".join([b for b in scope_bits if b])
    if scope:
        sentence = f"{intent} ({scope})."
    else:
        sentence = f"{intent}."

    # Ensure it's one sentence
    sentence = re.sub(r"\s+", " ", sentence).strip()
    return sentence

