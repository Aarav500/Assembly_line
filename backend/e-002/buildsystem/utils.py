import os
import yaml
from typing import List, Dict, Any


def load_yaml_files(paths: List[str]) -> List[Dict[str, Any]]:
    results = []
    for p in paths:
        try:
            with open(p, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            results.append({'path': p, 'data': data})
        except FileNotFoundError:
            continue
    return results

