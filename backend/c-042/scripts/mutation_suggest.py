import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET


@dataclass
class Survivor:
    id: Optional[int]
    file: Optional[Path]
    line: Optional[int]
    raw: Dict


def _run(cmd: List[str]) -> Tuple[int, str, str]:
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def run_mutmut(skip_run: bool = False) -> None:
    if skip_run:
        return
    rc, out, err = _run([sys.executable, "-m", "pytest", "-q"])  # warm up coverage
    if rc != 0:
        print("Tests failed before mutation run. Fix tests first.")
        print(out)
        print(err, file=sys.stderr)
        sys.exit(2)

    rc, out, err = _run(["mutmut", "run", "--no-progress"])
    if rc != 0:
        print("mutmut run failed:")
        print(out)
        print(err, file=sys.stderr)
        sys.exit(2)


def _parse_mutmut_results_json(payload: str) -> List[Survivor]:
    survivors: List[Survivor] = []
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return survivors

    # Accept a few possible shapes
    items: List[Dict] = []
    if isinstance(data, dict):
        if "survived" in data and isinstance(data["survived"], list):
            items = data["survived"]
        elif "mutants" in data and isinstance(data["mutants"], list):
            items = [m for m in data["mutants"] if m.get("status") == "survived"]
    elif isinstance(data, list):
        items = [m for m in data if m.get("status") == "survived"]

    for m in items:
        file_key = None
        for k in ("file", "module", "path"):
            if k in m:
                file_key = k
                break
        file_path = Path(m[file_key]) if file_key else None
        line_no = m.get("line") or m.get("line_no") or m.get("lineno")
        mid = m.get("id")
        survivors.append(Survivor(id=mid, file=file_path, line=line_no, raw=m))
    return survivors


def _parse_mutmut_results_text(payload: str) -> List[Survivor]:
    """Best-effort parse of text results to locate file:line and optionally ids."""
    survivors: List[Survivor] = []
    # Try to capture entries like: "123 survived app/calculator.py:42" or "survived app/calculator.py:42"
    pattern = re.compile(r"(?m)^(?:(?P<id>\d+)\s+)?survived.*?(?P<file>[\w./\\-]+\.py):(?P<line>\d+)")
    for m in pattern.finditer(payload):
        mid = int(m.group("id")) if m.group("id") else None
        f = Path(m.group("file")).resolve()
        line = int(m.group("line"))
        survivors.append(Survivor(id=mid, file=f, line=line, raw={"source": "text"}))

    # If no file:line was available, try to find bare ids like lines starting with "123 survived"
    if not survivors:
        id_pattern = re.compile(r"(?m)^(?P<id>\d+)\s+survived\b")
        for m in id_pattern.finditer(payload):
            survivors.append(Survivor(id=int(m.group("id")), file=None, line=None, raw={"source": "text-ids"}))
    return survivors


def get_survivors() -> List[Survivor]:
    # Try JSON output
    rc, out, err = _run(["mutmut", "results", "--json"])
    if rc == 0 and out.strip():
        s = _parse_mutmut_results_json(out)
        if s:
            return s
    # Fallback to text parsing
    rc, out, err = _run(["mutmut", "results"])
    if rc == 0 and out.strip():
        return _parse_mutmut_results_text(out)
    # Nothing found
    return []


def _read_coverage_hits(coverage_xml: Path) -> Dict[Path, Dict[int, int]]:
    hits: Dict[Path, Dict[int, int]] = {}
    if not coverage_xml.exists():
        return hits
    try:
        tree = ET.parse(coverage_xml)
        root = tree.getroot()
        # Cobertura XML style
        for cls in root.findall(".//class"):
            filename = cls.get("filename")
            if not filename:
                continue
            fpath = Path(filename)
            line_hits: Dict[int, int] = {}
            for line in cls.findall("lines/line"):
                num = int(line.get("number"))
                cnt = int(line.get("hits"))
                line_hits[num] = cnt
            hits[fpath] = line_hits
    except Exception:
        pass
    return hits


def _get_context_lines(path: Path, line_no: int, context: int = 1) -> Tuple[str, List[str]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return "", []
    idx = max(0, line_no - 1)
    window = lines[max(0, idx - context) : min(len(lines), idx + context + 1)]
    return lines[idx] if 0 <= idx < len(lines) else "", window


def _analyze_code_line(code_line: str) -> List[str]:
    s: List[str] = []
    line = code_line.strip()

    # Comparison boundary suggestions
    if any(op in line for op in ("==", "!=", ">", ">=", "<", "<=")):
        s.append("Add tests that exercise both True and False outcomes of this comparison.")
        if ">=" in line or ">" in line:
            s.append("Include edge-case tests on the greater-than boundary (exactly equal and just above/below).")
        if "<=" in line or "<" in line:
            s.append("Include edge-case tests on the less-than boundary (exactly equal and just above/below).")
        if "==" in line or "!=" in line:
            s.append("Include tests where the compared values are equal and not equal.")

    # Boolean logic suggestions
    if re.search(r"\band\b", line) or re.search(r"\bor\b", line):
        s.append("Add tests covering all boolean combinations of the operands (TT, TF, FT, FF).")

    # None checks
    if "is None" in line or "is not None" in line:
        s.append("Add tests for both None and non-None values to ensure correct branch coverage.")

    # Zero division guard pattern
    if re.search(r"\bb\s*==\s*0\b", line) or "ZeroDivisionError" in line or "/" in line:
        s.append("Add tests for zero and non-zero denominators, including when any default value applies.")

    # Return constants or literals
    if re.search(r"return\s+[-+]?\d+(\.\d+)?\b", line):
        s.append("Verify tests assert on exact returned constants in this branch.")

    # sign function hint
    if re.search(r"\bn\s*[<>]=?\s*0\b", line):
        s.append("Add tests for negative, zero, and positive inputs to cover all branches.")

    # Clamp-like pattern
    if re.search(r"\bn\s*[<>]=?\s*(lo|hi)\b", line) or "clamp" in line:
        s.append("Add tests for values below lower bound, within range, and above upper bound.")

    return s


def _analyze_diff(diff_text: str) -> List[str]:
    """Heuristic suggestions based on a unified diff from `mutmut show <id>`."""
    suggestions: List[str] = []
    changed_pairs: List[Tuple[str, str]] = []
    minus: Optional[str] = None
    for raw in diff_text.splitlines():
        if raw.startswith("-") and not raw.startswith("---"):
            minus = raw[1:].strip()
        elif raw.startswith("+") and not raw.startswith("+++") and minus is not None:
            plus = raw[1:].strip()
            changed_pairs.append((minus, plus))
            minus = None
        else:
            minus = None

    for before, after in changed_pairs:
        if ("==" in before and "!=" in after) or ("!=" in before and "==" in after):
            suggestions.append("Add tests covering both equal and non-equal comparisons.")
        if (">" in before and ">=" in after) or (">=" in before and ">" in after):
            suggestions.append("Add boundary tests where values are exactly equal to the threshold.")
        if ("<" in before and "<=" in after) or ("<=" in before and "<" in after):
            suggestions.append("Add boundary tests for the less-than threshold (equal case).")
        if re.search(r"\band\b", before) and re.search(r"\bor\b", after) or re.search(r"\bor\b", before) and re.search(r"\band\b", after):
            suggestions.append("Boolean operator flip detected; add tests for TF and FT cases.")
        if ("True" in before and "False" in after) or ("False" in before and "True" in after):
            suggestions.append("Literal boolean change detected; ensure condition is asserted under both outcomes.")
        if re.search(r"\breturn\s+[-+]?\d+\b", before) and re.search(r"\breturn\s+[-+]?\d+\b", after):
            suggestions.append("Return constant mutated; assert exact constant value in tests.")

    return list(dict.fromkeys(suggestions))  # de-duplicate preserving order


def suggest_fixes(survivors: List[Survivor], coverage_xml: Path) -> List[Dict]:
    coverage_hits = _read_coverage_hits(coverage_xml)
    suggestions: List[Dict] = []

    for s in survivors:
        entry: Dict = {
            "id": s.id,
            "file": str(s.file) if s.file else None,
            "line": s.line,
            "code_context": None,
            "suggestions": [],
        }

        # Try to fetch diff if id is available
        diff_suggestions: List[str] = []
        if s.id is not None:
            rc, out, err = _run(["mutmut", "show", str(s.id)])
            if rc == 0 and out:
                diff_suggestions = _analyze_diff(out)
        entry["suggestions"].extend(diff_suggestions)

        # Code-line heuristics
        if s.file and s.line:
            code_line, ctx = _get_context_lines(Path(s.file), s.line, context=1)
            entry["code_context"] = {
                "line": code_line,
                "window": ctx,
            }
            entry["suggestions"].extend(_analyze_code_line(code_line))

            # Coverage hints
            hits_for_file = coverage_hits.get(Path(s.file)) or coverage_hits.get(Path(os.path.relpath(s.file)))
            if hits_for_file is not None:
                hits = hits_for_file.get(s.line, 0)
                if hits == 0:
                    entry["suggestions"].append("Line appears uncovered in coverage; add a test to execute this branch.")
        else:
            entry["suggestions"].append(
                "Could not resolve file/line from results; re-run with `mutmut results --json` for better suggestions."
            )

        # De-duplicate
        entry["suggestions"] = list(dict.fromkeys(entry["suggestions"]))
        suggestions.append(entry)

    return suggestions


def main(argv: List[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run mutation testing and suggest fixes for survived mutants.")
    parser.add_argument("--skip-run", action="store_true", help="Skip running mutmut; only analyze existing results.")
    parser.add_argument("--coverage-xml", type=Path, default=Path("coverage.xml"), help="Path to coverage.xml for hit analysis.")
    parser.add_argument("--output", type=Path, default=None, help="Optional path to write JSON suggestions.")
    args = parser.parse_args(argv)

    run_mutmut(skip_run=args.skip_run)

    survivors = get_survivors()
    if not survivors:
        print(json.dumps({"message": "No survivors found or unable to parse results.", "survivors": []}, indent=2))
        return 0

    suggestions = suggest_fixes(survivors, args.coverage_xml)

    payload = {
        "summary": {
            "total_survivors": len(survivors),
        },
        "survivors": suggestions,
    }

    text = json.dumps(payload, indent=2)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

