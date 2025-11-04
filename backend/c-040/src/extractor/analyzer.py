import os
from collections import defaultdict
from bs4 import BeautifulSoup
from .html_utils import parse_html, candidate_roots, normalize_tag, guess_component_name


def analyze_directory(root_dir: str, min_occurrences=2, min_length=200, max_components=20):
    # signature -> data
    occurrences = {}
    counts = defaultdict(int)
    example_files = defaultdict(set)
    samples = {}

    html_files = []
    for base, _, files in os.walk(root_dir):
        for f in files:
            if f.lower().endswith(('.html', '.htm')):
                html_files.append(os.path.join(base, f))

    for path in html_files:
        with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
            content = fh.read()
        soup = parse_html(content)
        for tag in candidate_roots(soup):
            norm = normalize_tag(tag)
            if len(norm.normalized) < min_length:
                continue
            counts[norm.signature] += 1
            example_files[norm.signature].add(os.path.relpath(path, root_dir))
            if norm.signature not in samples:
                samples[norm.signature] = {
                    'normalized': norm.normalized,
                    'placeholders': [
                        {
                            'type': ph.type,
                            'path': ph.path,
                            'attr': ph.attr,
                            'name': ph.name
                        } for ph in norm.placeholders
                    ],
                    'size': norm.size,
                    'tag_name': tag.name,
                    'classes': tag.get('class', []) if isinstance(tag.get('class', []), list) else []
                }

    # Filter candidates
    candidates = []
    used_names = set()
    for sig, cnt in sorted(counts.items(), key=lambda x: -x[1]):
        if cnt < min_occurrences:
            continue
        samp = samples.get(sig)
        if not samp:
            continue
        name = guess_component_name(BeautifulSoup(samp['normalized'], 'lxml').find(), used_names)  # reconstruct tag to guess name
        used_names.add(name)
        candidates.append({
            'name': name,
            'signature': sig,
            'placeholders': samp['placeholders'],
            'size': samp['size'],
            'occurrences': cnt,
            'example_files': sorted(example_files[sig])
        })
        if len(candidates) >= max_components:
            break

    return {
        'components': candidates,
        'total_html_files': len(html_files)
    }

