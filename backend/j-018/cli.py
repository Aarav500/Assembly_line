#!/usr/bin/env python3
import argparse
import json
import os
import sys
from typing import List, Tuple

from accessibility.analyzer import analyze_html


def find_files(paths: List[str], exts: Tuple[str, ...]) -> List[str]:
    found: List[str] = []
    for p in paths:
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in files:
                    if f.lower().endswith(exts):
                        found.append(os.path.join(root, f))
        elif os.path.isfile(p) and p.lower().endswith(exts):
            found.append(p)
    return sorted(set(found))


def main():
    parser = argparse.ArgumentParser(description='Accessibility analyzer for HTML templates')
    parser.add_argument('paths', nargs='*', help='Files or directories to scan (defaults to ./templates)')
    parser.add_argument('--format', choices=['text', 'json'], default='text', help='Output format')
    parser.add_argument('--level', choices=['error', 'warning', 'info'], default='error', help='Fail on severity level or above')
    parser.add_argument('--max-warnings', type=int, default=None, help='Maximum allowed warnings before failure')
    parser.add_argument('--max-info', type=int, default=None, help='Maximum allowed info before failure')
    args = parser.parse_args()

    targets = args.paths or ['templates']
    files = find_files(targets, ('.html', '.htm', '.jinja', '.jinja2', '.tpl'))

    if not files:
        print('No files found to analyze.', file=sys.stderr)
        sys.exit(0)

    overall = []
    totals = {'errors': 0, 'warnings': 0, 'info': 0, 'total': 0}

    for fpath in files:
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                html = f.read()
            result = analyze_html(html, base_url=None)
            overall.append({'file': fpath, **result})
            for k in ['errors', 'warnings', 'info', 'total']:
                totals[k] += result['stats'][k]
        except Exception as e:
            print(f'Failed to analyze {fpath}: {e}', file=sys.stderr)

    if args.format == 'json':
        print(json.dumps({'summary': totals, 'files': overall}, indent=2))
    else:
        print('Accessibility report:')
        print(f"  Files analyzed: {len(files)}")
        print(f"  Errors:   {totals['errors']}")
        print(f"  Warnings: {totals['warnings']}")
        print(f"  Info:     {totals['info']}")
        for f in overall:
            stats = f['stats']
            if stats['total'] == 0:
                continue
            print(f"\nFile: {f['file']}")
            print(f"  Errors: {stats['errors']}  Warnings: {stats['warnings']}  Info: {stats['info']}")
            for iss in f['issues']:
                print(f"   - [{iss['severity']}] {iss['code']}: {iss['message']}")
                if iss.get('selector'):
                    print(f"     selector: {iss['selector']}")
                if iss.get('context'):
                    print(f"     context: {iss['context']}")

    # determine exit code based on thresholds
    fail = False
    level = args.level
    if level == 'error' and totals['errors'] > 0:
        fail = True
    elif level == 'warning' and (totals['errors'] + totals['warnings'] > 0):
        fail = True
    elif level == 'info' and totals['total'] > 0:
        fail = True

    if args.max_warnings is not None and totals['warnings'] > args.max_warnings:
        fail = True
    if args.max_info is not None and totals['info'] > args.max_info:
        fail = True

    sys.exit(1 if fail else 0)


if __name__ == '__main__':
    main()

