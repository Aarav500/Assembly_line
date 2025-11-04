import csv
import os
import re
from collections import Counter
from statistics import mean, median, pstdev
from typing import Any, Dict, List


NUMERIC_MATCH = re.compile(r'^[-+]?\d*\.?\d+(e[-+]?\d+)?$', re.IGNORECASE)
WORD_RE = re.compile(r"[\w']+")


def try_float(x: str):
    try:
        return float(x)
    except Exception:
        return None


def analyze_csv(path: str) -> Dict[str, Any]:
    # Read CSV and compute per-column basic stats without external deps.
    with open(path, 'r', newline='', encoding='utf-8', errors='replace') as f:
        sample = f.read(2048)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample)
        except Exception:
            dialect = csv.excel
        reader = csv.reader(f, dialect)
        try:
            header = next(reader)
        except StopIteration:
            return {"type": "csv", "rows": 0, "columns": 0, "columns_stats": {}, "note": "Empty file"}

        num_cols = len(header)
        cols = [
            {
                'name': header[i],
                'count': 0,
                'missing': 0,
                'numeric_count': 0,
                'non_numeric_count': 0,
                'min': None,
                'max': None,
                'sum': 0.0,
                'values_numeric': [],
                'top_values': Counter(),
                'unique_tracking': set(),
                'unique_limit_hit': False
            } for i in range(num_cols)
        ]

        row_count = 0
        UNIQUE_TRACK_LIMIT = 100000
        TOP_K = 5

        for row in reader:
            row_count += 1
            # Pad or trim row to match header length
            if len(row) < num_cols:
                row = row + [''] * (num_cols - len(row))
            elif len(row) > num_cols:
                row = row[:num_cols]

            for i, raw in enumerate(row):
                c = cols[i]
                c['count'] += 1
                val = raw.strip()
                if val == '' or val.lower() in {'na', 'null', 'none'}:
                    c['missing'] += 1
                else:
                    # Track unique values with a cap to avoid excessive memory usage
                    if not c['unique_limit_hit']:
                        c['unique_tracking'].add(val)
                        if len(c['unique_tracking']) > UNIQUE_TRACK_LIMIT:
                            c['unique_tracking'].clear()
                            c['unique_limit_hit'] = True

                    # Track top value frequencies (capped internally by most_common)
                    c['top_values'][val] += 1

                    # Numeric detection
                    v = try_float(val) if NUMERIC_MATCH.match(val) else None
                    if v is not None:
                        c['numeric_count'] += 1
                        c['sum'] += v
                        c['values_numeric'].append(v)
                        if c['min'] is None or v < c['min']:
                            c['min'] = v
                        if c['max'] is None or v > c['max']:
                            c['max'] = v
                    else:
                        c['non_numeric_count'] += 1

        # Build result
        columns_stats: List[Dict[str, Any]] = []
        for c in cols:
            is_numeric = c['numeric_count'] > 0 and c['non_numeric_count'] == 0
            col_stat: Dict[str, Any] = {
                'name': c['name'],
                'count': c['count'],
                'missing': c['missing'],
                'unique_count': ('> ' + str(100000)) if c['unique_limit_hit'] else len(c['unique_tracking']),
                'top_values': [
                    {'value': v, 'count': cnt}
                    for v, cnt in c['top_values'].most_common(TOP_K)
                ],
                'is_numeric': is_numeric
            }
            if is_numeric:
                nums = c['values_numeric']
                if nums:
                    col_stat.update({
                        'min': c['min'],
                        'max': c['max'],
                        'mean': c['sum'] / len(nums),
                        'median': median(nums),
                        'stdev_pop': pstdev(nums) if len(nums) > 1 else 0.0
                    })
                else:
                    col_stat.update({'min': None, 'max': None, 'mean': None, 'median': None, 'stdev_pop': None})
            columns_stats.append(col_stat)

        return {
            'type': 'csv',
            'rows': row_count,
            'columns': num_cols,
            'columns_stats': columns_stats
        }


def analyze_txt(path: str) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        text = f.read()
    lines = text.splitlines()
    words = WORD_RE.findall(text.lower())
    total_words = len(words)
    total_chars = len(text)
    top_words = Counter(words).most_common(10)
    avg_word_len = mean([len(w) for w in words]) if words else 0.0

    return {
        'type': 'text',
        'lines': len(lines),
        'words': total_words,
        'characters': total_chars,
        'average_word_length': avg_word_len,
        'top_words': [{'word': w, 'count': c} for w, c in top_words]
    }


def analyze_file(path: str) -> Dict[str, Any]:
    if not os.path.isfile(path):
        raise FileNotFoundError(f'File not found: {path}')
    ext = os.path.splitext(path)[1].lower()
    if ext == '.csv':
        return analyze_csv(path)
    elif ext in {'.txt', '.log'}:
        return analyze_txt(path)
    else:
        # Fallback: attempt CSV, else treat as text
        try:
            return analyze_csv(path)
        except Exception:
            return analyze_txt(path)

