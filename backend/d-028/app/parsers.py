import re
from typing import Dict, List, Optional, Tuple


class ReproData:
    def __init__(self, failing_tests: List[str], failing_files: List[str], language: Optional[str], commands: List[str], summary: str):
        self.failing_tests = failing_tests
        self.failing_files = failing_files
        self.language = language
        self.commands = commands
        self.summary = summary

    def to_markdown(self) -> str:
        lines = []
        lines.append("Summary:\n" + (self.summary or ""))
        if self.failing_tests:
            lines.append("Failing tests:")
            for t in self.failing_tests:
                lines.append(f"- {t}")
        if self.failing_files:
            lines.append("Failing files:")
            for f in self.failing_files:
                lines.append(f"- {f}")
        if self.commands:
            lines.append("\nReproduction steps:")
            for c in self.commands:
                lines.append(f"- {c}")
        return "\n".join(lines)


def parse_r_testthat_logs(log_text: str) -> Optional[ReproData]:
    # Look for testthat style outputs
    # Patterns include lines like:
    #   ── 1. Failure: some test description (@test-something.R#12)  ────────────────
    #   Failure (test-something.R:12): description
    # Also summary at end:
    #   Failed tests: test-something.R:12: ...
    failing_tests = []
    failing_files = []

    # Capture failure blocks
    for m in re.finditer(r"Failure \(?(?P<file>[^:]+):(\d+)\)?: (?P<desc>.+)", log_text):
        desc = m.group("desc").strip()
        failing_tests.append(desc)
        failing_files.append(m.group("file").strip())

    # Capture testthat 3.x style
    for m in re.finditer(r"\u2500\u2500\s+\d+\.\s+(Failure|Error):\s+(?P<desc>.+?)\s+\(@(?P<file>test-[^#]+)#\d+\)", log_text):
        failing_tests.append(m.group("desc").strip())
        failing_files.append(m.group("file").strip())

    # Additional capture: lines with test-*.R and expectation failure
    for m in re.finditer(r"(?P<file>test-[\w\-_.]+\.R).*?(expect_[\w]+).*?failed", log_text, flags=re.IGNORECASE | re.DOTALL):
        failing_files.append(m.group("file"))

    failing_tests = list(dict.fromkeys([t for t in failing_tests if t]))
    failing_files = list(dict.fromkeys([f for f in failing_files if f]))

    if not failing_tests and not failing_files:
        return None

    commands = [
        "git fetch --all --tags",
        "git checkout <commit-sha>",
        "R -q -e 'sessionInfo()'",
    ]

    if failing_files:
        # Construct a filter pattern for devtools::test
        pattern = "|".join([re.escape(f.replace("test-", "").replace(".R", "")) for f in failing_files])
        if pattern:
            commands.append(f"R -q -e 'if (requireNamespace(\"devtools\", quietly=TRUE)) devtools::test(filter=\"{pattern}\") else testthat::test_dir(\"tests/testthat\", filter=\"{pattern}\")'")
        else:
            commands.append("R -q -e 'devtools::test()'")
    else:
        commands.append("R -q -e 'devtools::test()'")

    summary = "R testthat failures detected."

    return ReproData(failing_tests=failing_tests, failing_files=failing_files, language="R", commands=commands, summary=summary)


def parse_pytest_logs(log_text: str) -> Optional[ReproData]:
    # Basic pytest parsing as fallback
    failing_tests = []
    failing_files = []

    # Collect lines like: FAILED tests/test_module.py::TestClass::test_thing - AssertionError: ...
    for m in re.finditer(r"FAILED\s+(?P<file>[^\s:]+(?:\.py)?)::(?P<nodeid>[^\s]+)\s+-\s+(?P<reason>.+)", log_text):
        node = m.group("nodeid").strip()
        failing_tests.append(node)
        failing_files.append(m.group("file").strip())

    # Collect summary like: 1 failed, 20 passed in 3.21s
    summary_match = re.search(r"(\d+)\s+failed,.*in\s+[\d\.]+s", log_text)
    summary = summary_match.group(0) if summary_match else "Pytest failures detected."

    if not failing_tests and not failing_files:
        return None

    commands = [
        "git fetch --all --tags",
        "git checkout <commit-sha>",
        "python -m venv .venv && . .venv/bin/activate",
        "pip install -U pip",
        "pip install -e .[test]",
    ]

    if failing_files:
        commands.append(f"pytest {' '.join(set(failing_files))} -q")
    else:
        commands.append("pytest -q")

    return ReproData(failing_tests=list(dict.fromkeys(failing_tests)), failing_files=list(dict.fromkeys(failing_files)), language="Python", commands=commands, summary=summary)


def extract_repro(log_text: str) -> ReproData:
    # Try language-specific parsers
    for parser in (parse_r_testthat_logs, parse_pytest_logs):
        try:
            rd = parser(log_text)
            if rd:
                return rd
        except Exception:
            continue
    # Fallback generic
    commands = [
        "git fetch --all --tags",
        "git checkout <commit-sha>",
        "# Run your project's test command here",
    ]
    return ReproData(failing_tests=[], failing_files=[], language=None, commands=commands, summary="CI failure detected.")


def build_issue_body(repo_full_name: str, run_html_url: str, run_id: int, head_sha: str, repro: ReproData, failing_jobs: List[str]) -> str:
    parts = []
    parts.append(f"Automated issue created from failed CI run: {run_html_url}")
    parts.append("")
    parts.append(f"Repository: {repo_full_name}")
    parts.append(f"Run ID: {run_id}")
    parts.append(f"Commit: {head_sha}")
    if failing_jobs:
        parts.append("Failed jobs:")
        for j in failing_jobs:
            parts.append(f"- {j}")
    parts.append("")
    parts.append(repro.to_markdown())
    parts.append("")
    parts.append("This issue was auto-generated by ci-repro-bot.")
    return "\n".join(parts)


def build_pr_body(repo_full_name: str, run_html_url: str, run_id: int, head_sha: str, repro: ReproData) -> str:
    parts = []
    parts.append(f"Automated PR adding minimal reproduction scaffolding for failed CI run: {run_html_url}")
    parts.append("")
    parts.append(f"Repository: {repo_full_name}")
    parts.append(f"Run ID: {run_id}")
    parts.append(f"Commit: {head_sha}")
    parts.append("")
    parts.append(repro.to_markdown())
    parts.append("")
    parts.append("This PR was auto-generated by ci-repro-bot and may be marked as draft.")
    return "\n".join(parts)


def make_r_repro_script(repro: ReproData, run_id: int, head_sha: str) -> str:
    filter_cmd = None
    if repro.failing_files:
        pattern = "|".join([f.replace("test-", "").replace(".R", "") for f in repro.failing_files])
        filter_cmd = f"\"{pattern}\""
    commands = []
    commands.append("# Auto-generated reproduction script for R testthat failures")
    commands.append(f"# Run ID: {run_id}")
    commands.append(f"# Commit: {head_sha}")
    commands.append("# Prerequisites: R, devtools and testthat installed")
    commands.append("print(sessionInfo())")
    if filter_cmd:
        commands.append(f"if (requireNamespace('devtools', quietly=TRUE)) devtools::test(filter={filter_cmd}) else testthat::test_dir('tests/testthat', filter={filter_cmd})")
    else:
        commands.append("if (requireNamespace('devtools', quietly=TRUE)) devtools::test() else testthat::test_dir('tests/testthat')")
    return "\n".join(commands) + "\n"


def make_text_repro_notes(repro: ReproData, run_id: int, head_sha: str) -> str:
    lines = []
    lines.append("Auto-generated reproduction notes")
    lines.append(f"Run ID: {run_id}")
    lines.append(f"Commit: {head_sha}")
    lines.append("")
    lines.append(repro.to_markdown())
    return "\n".join(lines) + "\n"

