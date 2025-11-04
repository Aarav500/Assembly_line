import os
import re
import logging
from typing import Any
from .utils import iter_files, read_text, slugify, unique_by_slug, best_name, guess_test_dirs


class FeatureDetector:
    def __init__(self, options: dict | None = None):
        self.options = options or {}

    def detect_features(self, repo_path: str) -> list[dict[str, Any]]:
        """Detect features from repository code"""
        features: list[dict[str, Any]] = []
        try:
            # Scan Python files for route definitions, API endpoints, etc.
            for fpath in iter_files(repo_path, [".py"]):
                try:
                    content = read_text(fpath)
                    features.extend(self._extract_flask_routes(fpath, content))
                except Exception as e:
                    logging.error(f"Error processing {fpath}: {e}")
                    continue
            return unique_by_slug(features)
        except Exception as e:
            logging.error(f"Error detecting features: {e}")
            return []

    def _extract_flask_routes(self, fpath: str, content: str) -> list[dict[str, Any]]:
        """Extract Flask route definitions as features"""
        features: list[dict[str, Any]] = []
        try:
            # Match Flask route decorators
            route_pattern = r'@app\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']\)'
            for match in re.finditer(route_pattern, content):
                method = match.group(1).upper()
                path = match.group(2)
                name = f"{method} {path}"
                features.append({
                    "name": name,
                    "slug": slugify(name),
                    "kind": "api_endpoint",
                    "source": fpath,
                    "criticality": "medium",
                    "tags": [method.lower(), "api"],
                    "metadata": {"method": method, "path": path}
                })
        except Exception as e:
            logging.error(f"Error extracting Flask routes: {e}")
        return features

    def merge_features(self, detected: list[dict], provided: list[dict]) -> list[dict]:
        """Merge detected features with user-provided features"""
        try:
            combined = detected + provided
            return unique_by_slug(combined)
        except Exception as e:
            logging.error(f"Error merging features: {e}")
            return detected


class AcceptanceTestDetector:
    def __init__(self, options: dict | None = None):
        self.options = options or {}

    def detect_acceptance_tests(self, repo_path: str) -> list[dict[str, Any]]:
        """Detect acceptance tests from repository"""
        tests: list[dict[str, Any]] = []
        try:
            test_dirs = guess_test_dirs(repo_path)
            for test_dir in test_dirs:
                for fpath in iter_files(test_dir, [".py", ".feature"]):
                    try:
                        content = read_text(fpath)
                        if fpath.endswith(".py"):
                            tests.extend(self._extract_pytest_tests(fpath, content))
                        elif fpath.endswith(".feature"):
                            tests.extend(self._extract_gherkin_tests(fpath, content))
                    except Exception as e:
                        logging.error(f"Error processing test file {fpath}: {e}")
                        continue
            return unique_by_slug(tests, key="name")
        except Exception as e:
            logging.error(f"Error detecting acceptance tests: {e}")
            return []

    def _extract_pytest_tests(self, fpath: str, content: str) -> list[dict[str, Any]]:
        """Extract pytest test functions"""
        tests: list[dict[str, Any]] = []
        try:
            # Match test function definitions
            test_pattern = r'def (test_[a-zA-Z0-9_]+)\s*\('
            for match in re.finditer(test_pattern, content):
                test_name = match.group(1)
                # Try to infer covered features from test name
                features = self._infer_features_from_test_name(test_name)
                tests.append({
                    "name": test_name,
                    "slug": slugify(test_name),
                    "source": fpath,
                    "type": "pytest",
                    "features": features
                })
        except Exception as e:
            logging.error(f"Error extracting pytest tests: {e}")
        return tests

    def _extract_gherkin_tests(self, fpath: str, content: str) -> list[dict[str, Any]]:
        """Extract Gherkin/Cucumber scenarios"""
        tests: list[dict[str, Any]] = []
        try:
            # Match Gherkin scenarios
            scenario_pattern = r'Scenario:\s*(.+)'
            for match in re.finditer(scenario_pattern, content):
                scenario_name = match.group(1).strip()
                features = self._infer_features_from_test_name(scenario_name)
                tests.append({
                    "name": scenario_name,
                    "slug": slugify(scenario_name),
                    "source": fpath,
                    "type": "gherkin",
                    "features": features
                })
        except Exception as e:
            logging.error(f"Error extracting Gherkin tests: {e}")
        return tests

    def _infer_features_from_test_name(self, test_name: str) -> list[dict[str, str]]:
        """Infer which features a test covers based on its name"""
        features: list[dict[str, str]] = []
        try:
            # Extract potential feature references from test name
            # e.g., test_health_endpoint -> health
            name_lower = test_name.lower().replace("test_", "").replace("_", " ")
            slug = slugify(name_lower)
            if slug:
                features.append({
                    "name": name_lower,
                    "slug": slug
                })
        except Exception as e:
            logging.error(f"Error inferring features: {e}")
        return features

    def merge_tests(self, detected: list[dict], provided: list[dict]) -> list[dict]:
        """Merge detected tests with user-provided tests"""
        try:
            combined = detected + provided
            return unique_by_slug(combined, key="name")
        except Exception as e:
            logging.error(f"Error merging tests: {e}")
            return detected