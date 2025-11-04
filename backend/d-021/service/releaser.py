import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from config import settings
from service.github_client import GitHubClient
from service.changelog import render_changelog, filter_release_worthy

logger = logging.getLogger(__name__)

SEMVER_RE = re.compile(r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)(?:[-+].*)?$")
CONV_RE = re.compile(r"^(?P<type>feat|fix|perf|refactor|docs|build|ci|test|style|chore)(?:\((?P<scope>[^)]+)\))?(?P<bang>!)?: (?P<description>.+)")


@dataclass
class Version:
    major: int
    minor: int
    patch: int

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    @classmethod
    def parse(cls, s: str) -> Optional["Version"]:
        m = SEMVER_RE.match(s)
        if not m:
            return None
        return cls(int(m.group("major")), int(m.group("minor")), int(m.group("patch")))

    def bump(self, level: str) -> "Version":
        if level == "major":
            return Version(self.major + 1, 0, 0)
        if level == "minor":
            return Version(self.major, self.minor + 1, 0)
        if level == "patch":
            return Version(self.major, self.minor, self.patch + 1)
        return Version(self.major, self.minor, self.patch)


class ReleaseManager:
    def __init__(self):
        self.gh = GitHubClient()

    def handle_commits_event(self, repo_full_name: str, commits: List[Dict], head_sha: str) -> Dict:
        changes = [self._parse_commit_payload(c) for c in commits]
        return self._prepare_and_release(repo_full_name, changes, head_sha)

    def handle_pull_request_merged(self, repo_full_name: str, pr: Dict) -> Dict:
        pr_number = pr.get("number")
        head_sha = pr.get("merge_commit_sha") or pr.get("head", {}).get("sha")
        commits = self.gh.get_pull_request_commits(repo_full_name, pr_number)
        changes = []
        # Include the PR itself as a change item for visibility
        pr_change = {
            "type": self._type_from_labels(pr.get("labels", [])) or self._type_from_title(pr.get("title", "")),
            "scope": None,
            "description": pr.get("title", ""),
            "breaking": self._is_breaking_from_text(pr.get("body") or "") or self._has_breaking_label(pr.get("labels", [])),
            "pr_number": pr_number,
            "sha": head_sha,
        }
        changes.append(pr_change)
        for c in commits:
            parsed = self._parse_commit_payload({
                "id": c.get("sha"),
                "message": c.get("commit", {}).get("message", ""),
                "author": c.get("commit", {}).get("author", {}).get("name"),
                "url": c.get("html_url"),
            })
            parsed["pr_number"] = pr_number
            changes.append(parsed)
        return self._prepare_and_release(repo_full_name, changes, head_sha)

    def _prepare_and_release(self, repo_full_name: str, changes: List[Dict], head_sha: str) -> Dict:
        # Determine bump level
        bump = self._determine_bump(changes)
        if not bump:
            if settings.MIN_BUMP_IF_EMPTY == "none":
                return {"skipped": True, "reason": "No release-worthy changes"}
            bump = settings.MIN_BUMP_IF_EMPTY

        latest_tag, latest_version = self._latest_version(repo_full_name)
        current_version = latest_version or Version(0, 0, 0)
        next_version = current_version.bump(bump)
        tag = f"{settings.RELEASE_PREFIX}{next_version}"

        worthy_changes = filter_release_worthy(changes)
        if not worthy_changes and settings.MIN_BUMP_IF_EMPTY == "none":
            return {"skipped": True, "reason": "No release-worthy changes"}

        changelog = render_changelog(tag, worthy_changes or changes, repo_full_name)
        if settings.CHANGELOG_HEADER:
            changelog = settings.CHANGELOG_HEADER + "\n\n" + changelog

        title = settings.RELEASE_TITLE_TEMPLATE.format(tag=tag, version=str(next_version))

        logger.info("Creating release %s at %s with bump=%s (from %s)", tag, head_sha, bump, latest_tag or "no-tag")
        result = self.gh.create_release(
            repo=repo_full_name or settings.REPO_FULL_NAME,
            tag_name=tag,
            target_commitish=head_sha,
            name=title,
            body=changelog,
            draft=False,
            prerelease=False,
        )
        return {
            "created": True,
            "tag": tag,
            "version": str(next_version),
            "from": str(current_version),
            "bump": bump,
            "release": result,
        }

    def _parse_commit_payload(self, commit: Dict) -> Dict:
        message = commit.get("message") or commit.get("title") or ""
        lines = message.splitlines()
        header = lines[0] if lines else ""
        body = "\n".join(lines[1:]) if len(lines) > 1 else ""
        m = CONV_RE.match(header)
        ctype = None
        scope = None
        description = header
        breaking = False
        if m:
            ctype = m.group("type")
            scope = m.group("scope")
            description = m.group("description")
            if m.group("bang"):
                breaking = True
        if not breaking:
            breaking = self._is_breaking_from_text(body)
        return {
            "type": ctype,
            "scope": scope,
            "description": description,
            "message": message,
            "breaking": breaking,
            "sha": commit.get("id") or commit.get("sha"),
        }

    def _has_breaking_label(self, labels: List[Dict]) -> bool:
        for l in labels or []:
            name = (l.get("name") or "").lower()
            if "breaking" in name or name in {"semver:major", "type:breaking"}:
                return True
        return False

    def _type_from_labels(self, labels: List[Dict]) -> Optional[str]:
        for l in labels or []:
            name = (l.get("name") or "").lower()
            if name in {"semver:major", "type:breaking"}:
                return "feat"  # treat as feature but will be marked breaking elsewhere
            if name in {"semver:minor", "type:feature", "feat"}:
                return "feat"
            if name in {"semver:patch", "type:bug", "bug", "fix"}:
                return "fix"
        return None

    def _type_from_title(self, title: str) -> Optional[str]:
        m = CONV_RE.match(title or "")
        if m:
            return m.group("type")
        return None

    def _is_breaking_from_text(self, text: str) -> bool:
        if not text:
            return False
        for line in text.splitlines():
            if line.strip().lower().startswith("breaking change"):
                return True
        return False

    def _determine_bump(self, changes: List[Dict]) -> Optional[str]:
        has_breaking = any(c.get("breaking") for c in changes)
        if has_breaking:
            return "major"
        has_feat = any((c.get("type") == "feat") for c in changes)
        if has_feat:
            return "minor"
        has_patch = any((c.get("type") in {"fix", "perf", "refactor"}) for c in changes)
        if has_patch:
            return "patch"
        return None

    def _latest_version(self, repo_full_name: str) -> Tuple[Optional[str], Optional[Version]]:
        # Prefer releases; fallback to tags
        tag_prefix = settings.RELEASE_PREFIX
        latest_release = self.gh.latest_release(repo_full_name)
        if latest_release and isinstance(latest_release, dict):
            tag_name = latest_release.get("tag_name")
            if tag_name and tag_name.startswith(tag_prefix):
                ver = Version.parse(tag_name[len(tag_prefix):])
                if ver:
                    return tag_name, ver
        # List tags and find the highest semver with prefix
        tags = self.gh.list_tags(repo_full_name)
        best_tag = None
        best_ver = None
        for t in tags:
            name = t.get("name")
            if not name or not name.startswith(tag_prefix):
                continue
            ver = Version.parse(name[len(tag_prefix):])
            if not ver:
                continue
            if not best_ver or self._compare_versions(ver, best_ver) > 0:
                best_ver = ver
                best_tag = name
        return best_tag, best_ver

    def _compare_versions(self, a: Version, b: Version) -> int:
        if a.major != b.major:
            return 1 if a.major > b.major else -1
        if a.minor != b.minor:
            return 1 if a.minor > b.minor else -1
        if a.patch != b.patch:
            return 1 if a.patch > b.patch else -1
        return 0

