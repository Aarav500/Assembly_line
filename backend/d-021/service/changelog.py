from collections import defaultdict
from typing import Dict, List, Tuple

# Maps conventional commit type to human-readable section
SECTION_TITLES = {
    "feat": "Features",
    "fix": "Bug Fixes",
    "perf": "Performance",
    "refactor": "Refactoring",
    "docs": "Documentation",
    "build": "Build System",
    "ci": "Continuous Integration",
    "test": "Tests",
    "style": "Style",
    "chore": "Chores",
}

RELEASE_WORTHY = {"feat", "fix", "perf", "refactor", "docs"}


def render_changelog(version_tag: str, changes: List[Dict], repo_full_name: str) -> str:
    groups: Dict[str, List[str]] = defaultdict(list)
    breaking_notes: List[str] = []

    for c in changes:
        ctype = c.get("type") or "other"
        scope = f"{c['scope']}: " if c.get("scope") else ""
        desc = c.get("description") or c.get("message") or ""
        pr_number = c.get("pr_number")
        sha = c.get("sha")
        breaking = c.get("breaking")

        link = None
        if pr_number:
            link = f"[#${pr_number}](https://github.com/{repo_full_name}/pull/{pr_number})"
        elif sha:
            link = f"[{sha[:7]}](https://github.com/{repo_full_name}/commit/{sha})"

        line = f"- {scope}{desc}"
        if link:
            line += f" ({link})"
        if breaking:
            breaking_notes.append(line)
        groups[ctype].append(line)

    lines: List[str] = []
    lines.append(f"## {version_tag}")
    lines.append("")

    if breaking_notes:
        lines.append("### Breaking Changes")
        lines.extend(breaking_notes)
        lines.append("")

    for ctype in SECTION_TITLES:
        section_lines = groups.get(ctype)
        if section_lines:
            lines.append(f"### {SECTION_TITLES[ctype]}")
            lines.extend(section_lines)
            lines.append("")

    # Any remaining types not predefined
    for ctype, section_lines in groups.items():
        if ctype in SECTION_TITLES:
            continue
        if section_lines:
            lines.append(f"### {ctype.title()}")
            lines.extend(section_lines)
            lines.append("")

    return "\n".join(lines).strip() + "\n"


def filter_release_worthy(changes: List[Dict]) -> List[Dict]:
    worthy = []
    for c in changes:
        if c.get("breaking"):
            worthy.append(c)
            continue
        ctype = c.get("type")
        if ctype in RELEASE_WORTHY:
            worthy.append(c)
    return worthy

