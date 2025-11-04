import os
import re
import uuid
from typing import List, Dict, Tuple

from .patterns import PATTERN_DEFINITIONS, SENSITIVE_FILENAME_GLOBS
from .utils import is_probably_binary, size_over_limit, match_any_glob, luhn_check, masked_context


class Scanner:
    reports: Dict[str, dict] = {}

    def __init__(self):
        # Pre-resolve post_filters
        self.patterns = []
        for p in PATTERN_DEFINITIONS:
            post = p.get('post_filter')
            if post == 'luhn':
                pf = self._luhn_post_filter
            else:
                pf = None
            self.patterns.append({**p, 'post_filter': pf})

    def scan(self,
             paths: List[str],
             include_patterns: List[str] = None,
             exclude_patterns: List[str] = None,
             max_file_size_mb: int = 10,
             follow_symlinks: bool = False,
             show_context: bool = True,
             ) -> Tuple[str, dict]:
        include_patterns = include_patterns or []
        exclude_patterns = exclude_patterns or []
        max_bytes = max(1, max_file_size_mb) * 1024 * 1024

        files_scanned = 0
        flagged_files = []
        errors = []

        to_scan = self._expand_paths(paths, follow_symlinks)

        for file_path in to_scan:
            rel_name = os.path.basename(file_path)
            rel_path = file_path

            # Exclude filters
            if match_any_glob(rel_name, exclude_patterns) or match_any_glob(rel_path, exclude_patterns):
                continue
            if include_patterns:
                if not (match_any_glob(rel_name, include_patterns) or match_any_glob(rel_path, include_patterns)):
                    continue

            try:
                if size_over_limit(file_path, max_bytes):
                    continue
                if is_probably_binary(file_path):
                    continue
                files_scanned += 1
                sensitive_name_reasons = self._sensitive_filename_reasons(rel_path)
                findings = self._scan_file(file_path, show_context)
                if sensitive_name_reasons or findings:
                    flagged_files.append({
                        'path': file_path,
                        'reasons': sensitive_name_reasons,
                        'findings': findings,
                    })
            except Exception as e:
                errors.append({'path': file_path, 'error': str(e)})

        summary = {
            'files_scanned': files_scanned,
            'files_flagged': len(flagged_files),
            'findings_count': sum(len(f.get('findings', [])) for f in flagged_files),
        }

        report = {
            'summary': summary,
            'flagged_files': flagged_files,
            'errors': errors,
        }

        scan_id = str(uuid.uuid4())
        Scanner.reports[scan_id] = report
        return scan_id, report

    def _expand_paths(self, paths: List[str], follow_symlinks: bool) -> List[str]:
        files = []
        for p in paths:
            if not p:
                continue
            p = os.path.abspath(p)
            if os.path.isfile(p):
                files.append(p)
            elif os.path.isdir(p):
                for root, dirs, filenames in os.walk(p, followlinks=follow_symlinks):
                    # Optionally skip hidden dirs like .git
                    dirs[:] = [d for d in dirs]
                    for n in filenames:
                        files.append(os.path.join(root, n))
            else:
                # Non-existent path is ignored
                continue
        return files

    def _sensitive_filename_reasons(self, rel_path: str) -> List[dict]:
        reasons = []
        # Check against known sensitive filename globs (on full relative path and base name)
        from .patterns import SENSITIVE_FILENAME_GLOBS
        base = os.path.basename(rel_path)
        normalized = rel_path.replace('\\', '/')
        for glob in SENSITIVE_FILENAME_GLOBS:
            if match_any_glob(base, [glob]) or match_any_glob(normalized, [glob]):
                reasons.append({'type': 'sensitive_filename', 'pattern': glob, 'severity': 'high'})
        return reasons

    def _scan_file(self, path: str, show_context: bool) -> List[dict]:
        findings = []
        with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
            for lineno, line in enumerate(fh, start=1):
                findings.extend(self._scan_line(line, lineno, show_context))
        return findings

    def _scan_line(self, line: str, lineno: int, show_context: bool) -> List[dict]:
        results = []
        for p in self.patterns:
            for m in p['regex'].finditer(line):
                matched = m.group(0)
                if p['post_filter'] and not p['post_filter'](matched):
                    continue
                start, end = m.start(), m.end()
                item = {
                    'type': p['name'],
                    'severity': p['severity'],
                    'line': lineno,
                    'start_col': start + 1,
                    'end_col': end,
                    'description': p.get('description', p['name']),
                }
                if show_context:
                    item['context'] = masked_context(line, start, end)
                results.append(item)
        return results

    @staticmethod
    def _luhn_post_filter(value: str) -> bool:
        return luhn_check(value)

    @staticmethod
    def redact_content(content: str, findings: List[dict], token: str = '[REDACTED]') -> str:
        # Apply redaction by replacing spans on the content. Findings may be out-of-order across lines; we process line by line.
        lines = content.splitlines(keepends=True)
        # Group findings by line
        by_line: Dict[int, List[Tuple[int, int]]] = {}
        for f in findings:
            ln = f.get('line')
            if ln is None:
                continue
            # Convert back to 0-based columns for slicing; end_col was 1-based inclusive-ish; treat as python slicing end index
            start = max(0, int(f.get('start_col', 1)) - 1)
            end = max(start, int(f.get('end_col', start)))
            by_line.setdefault(ln, []).append((start, end))
        # Redact each line with multiple spans; sort descending to keep indices stable
        for ln, spans in by_line.items():
            idx = ln - 1
            if idx < 0 or idx >= len(lines):
                continue
            s = lines[idx]
            for start, end in sorted(spans, key=lambda x: x[0], reverse=True):
                s = s[:start] + token + s[end:]
            lines[idx] = s
        return ''.join(lines)

