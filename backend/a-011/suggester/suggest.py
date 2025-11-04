import logging
from typing import Any
from .utils import slugify, priority_from_criticality

logger = logging.getLogger(__name__)


class SuggestionEngine:
    def __init__(self, options: dict | None = None):
        self.options = options or {}

    def suggest(self, features: list[dict[str, Any]], tests: list[dict[str, Any]]) -> list[dict[str, Any]]:
        try:
            covered_slugs = self._covered_feature_slugs(tests)
            out: list[dict[str, Any]] = []
            for f in features:
                try:
                    slug = f.get("slug") or slugify(f.get("name", ""))
                    if not slug:
                        continue
                    if slug in covered_slugs:
                        continue
                    suggestions = self._suggest_for_feature(f)
                    out.append({
                        "feature": {
                            "name": f.get("name"),
                            "slug": slug,
                            "kind": f.get("kind"),
                            "source": f.get("source"),
                            "criticality": f.get("criticality"),
                            "tags": f.get("tags") or [],
                            "metadata": f.get("metadata") or {},
                        },
                        "priority": priority_from_criticality(f.get("criticality")),
                        "reason": "No acceptance tests detected for this feature",
                        "suggested_tests": suggestions,
                    })
                except Exception as e:
                    # Log error and continue processing other features
                    logger.error(f"Error processing feature {f.get('name', 'unknown')}: {e}")
                    continue
            return out
        except Exception as e:
            logger.error(f"Error in suggest method: {e}")
            return []

    def summary(self, suggestions: list[dict], features: list[dict], tests: list[dict]) -> dict:
        try:
            covered = len(self._covered_feature_slugs(tests))
            total = len({(f.get("slug") or slugify(f.get("name", ""))) for f in features})
            missing = len(suggestions)
            return {
                "features_total": total,
                "features_covered": covered,
                "features_missing": missing,
                "coverage_ratio": float(covered) / float(total) if total else 0.0,
            }
        except Exception as e:
            logger.error(f"Error in summary method: {e}")
            return {
                "features_total": 0,
                "features_covered": 0,
                "features_missing": 0,
                "coverage_ratio": 0.0,
            }

    def _covered_feature_slugs(self, tests: list[dict[str, Any]]) -> set[str]:
        covered: set[str] = set()
        try:
            for t in tests:
                try:
                    for f in t.get("features") or []:
                        slug = f.get("slug") or slugify(f.get("name", ""))
                        if slug:
                            covered.add(slug)
                except Exception as e:
                    logger.error(f"Error processing test features: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error in _covered_feature_slugs: {e}")
        return covered

    def _suggest_for_feature(self, feature: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            kind = (feature.get("kind") or "").lower()
            metadata = feature.get("metadata") or {}
            tags = [str(t).lower() for t in (feature.get("tags") or [])]
            name = feature.get("name") or feature.get("slug")
            slug = feature.get("slug") or slugify(name)

            suggestions: list[dict[str, Any]] = []

            # Common scenario templates
            def add(name_sfx: str, purpose: str, steps_py: list[str], steps_gh: list[str], negative: bool = False):
                try:
                    suggestions.append({
                        "name": f"{name} - {name_sfx}",
                        "type": "negative" if negative else "positive",
                        "outline_pytest": self._pytest_outline(slug, steps_py),
                        "outline_gherkin": self._gherkin_outline(name, name_sfx, steps_gh),
                    })
                except Exception as e:
                    logger.error(f"Error adding suggestion: {e}")

            # Generate basic test suggestions
            if kind == "api_endpoint":
                method = metadata.get("method", "GET")
                path = metadata.get("path", "/")
                add(
                    "Happy Path",
                    "Test successful request",
                    [f"Send {method} request to {path}", "Assert 200 status", "Assert valid response"],
                    [f"When I send a {method} request to {path}", "Then I should receive a 200 status", "And the response should be valid"]
                )
                add(
                    "Error Handling",
                    "Test error scenarios",
                    [f"Send invalid {method} request to {path}", "Assert error status", "Assert error message"],
                    [f"When I send an invalid {method} request to {path}", "Then I should receive an error status", "And an error message should be returned"],
                    negative=True
                )
            else:
                # Generic feature test
                add(
                    "Basic Functionality",
                    "Test basic feature behavior",
                    ["Setup test environment", "Execute feature", "Verify expected outcome"],
                    ["Given the system is ready", "When I use the feature", "Then it should work as expected"]
                )

            return suggestions
        except Exception as e:
            logger.error(f"Error in _suggest_for_feature: {e}")
            return []

    def _pytest_outline(self, slug: str, steps: list[str]) -> str:
        """Generate pytest test outline"""
        try:
            test_name = f"test_{slug}"
            lines = [f"def {test_name}(client):"]
            lines.append('    """Test outline"""')
            for step in steps:
                lines.append(f"    # {step}")
            lines.append("    pass")
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Error generating pytest outline: {e}")
            return ""

    def _gherkin_outline(self, name: str, scenario: str, steps: list[str]) -> str:
        """Generate Gherkin test outline"""
        try:
            lines = [f"Feature: {name}", "", f"  Scenario: {scenario}"]
            for step in steps:
                lines.append(f"    {step}")
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Error generating Gherkin outline: {e}")
            return ""