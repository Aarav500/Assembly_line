#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
from typing import Dict
import xml.etree.ElementTree as ET

DURATIONS_PATH = Path("tests/.test_durations.json")
EWMA_ALPHA = 0.7  # weight recent measurements higher


def normalize_path(p: str) -> str:
    return Path(p).as_posix()


def parse_junit(junit_path: Path) -> Dict[str, float]:
    if not junit_path.exists():
        return {}
    try:
        tree = ET.parse(junit_path)
        root = tree.getroot()
    except ET.ParseError:
        return {}

    # pytest can produce <testsuite> or <testsuites> root
    testcases = []
    if root.tag.endswith('testsuites'):
        for suite in root:
            testcases.extend(suite.findall('.//testcase'))
    else:
        testcases = root.findall('.//testcase')

    per_file: Dict[str, float] = {}
    for tc in testcases:
        time_str = tc.attrib.get('time', '0')
        try:
            t = float(time_str)
        except ValueError:
            t = 0.0
        file_attr = tc.attrib.get('file')
        if not file_attr:
            # Fallback to classname -> path heuristic
            classname = tc.attrib.get('classname', '')
            if classname:
                mod_path = classname.replace('.', '/') + '.py'
                file_attr = mod_path
            else:
                continue
        key = normalize_path(file_attr)
        per_file[key] = per_file.get(key, 0.0) + t

    return per_file


def load_durations(path: Path) -> Dict[str, float]:
    if path.exists():
        try:
            return {k: float(v) for k, v in json.loads(path.read_text(encoding='utf-8')).items()}
        except Exception:
            return {}
    return {}


def save_durations(path: Path, data: Dict[str, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding='utf-8')


def ewma_update(old: float, new: float, alpha: float = EWMA_ALPHA) -> float:
    if old is None:
        return new
    return alpha * new + (1.0 - alpha) * old


def main():
    parser = argparse.ArgumentParser(description='Update test durations store from a JUnit XML report.')
    parser.add_argument('--junit', type=str, default='junit.xml', help='Path to JUnit XML file produced by pytest.')
    parser.add_argument('--durations-file', type=str, default=str(DURATIONS_PATH), help='Path to durations JSON file to update.')
    parser.add_argument('--alpha', type=float, default=EWMA_ALPHA, help='EWMA alpha for smoothing (0..1).')
    args = parser.parse_args()

    junit_path = Path(args.junit)
    durations_file = Path(args.durations_file)

    new_per_file = parse_junit(junit_path)
    if not new_per_file:
        # Nothing to update
        return

    store = load_durations(durations_file)

    for f, t in new_per_file.items():
        old = store.get(f)
        store[f] = ewma_update(old if old is not None else None, t, args.alpha)

    save_durations(durations_file, store)


if __name__ == '__main__':
    main()

