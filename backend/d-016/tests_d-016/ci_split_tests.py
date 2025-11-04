#!/usr/bin/env python3
import argparse
import glob
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

DEFAULT_GLOB = "tests/test_*.py"
DURATIONS_PATH = Path("tests/.test_durations.json")
DEFAULT_ESTIMATE = 1.0


def read_env_shard_config() -> Tuple[int, int]:
    # Priority: CLI args override env; env fallbacks supported
    # Supported env: SHARD_INDEX/SHARD_TOTAL, CI_NODE_INDEX/CI_NODE_TOTAL, CIRCLE_NODE_INDEX/CIRCLE_NODE_TOTAL
    idx = os.getenv("SHARD_INDEX") or os.getenv("CI_NODE_INDEX") or os.getenv("CIRCLE_NODE_INDEX")
    total = os.getenv("SHARD_TOTAL") or os.getenv("CI_NODE_TOTAL") or os.getenv("CIRCLE_NODE_TOTAL")
    try:
        idx_val = int(idx) if idx is not None else 0
        total_val = int(total) if total is not None else 1
    except ValueError:
        idx_val, total_val = 0, 1
    return idx_val, total_val


def load_durations(path: Path) -> Dict[str, float]:
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                # ensure float
                return {k: float(v) for k, v in data.items()}
        except Exception:
            pass
    return {}


def normalize_path(p: str) -> str:
    # Store as POSIX-style relative path
    return Path(p).as_posix()


def discover_tests(pattern: str) -> List[str]:
    files = glob.glob(pattern, recursive=True)
    # Filter to files that exist and are .py
    files = [normalize_path(f) for f in files if os.path.isfile(f) and f.endswith('.py')]
    files.sort()
    return files


def estimate_duration(file: str, durations: Dict[str, float]) -> float:
    if file in durations:
        return float(durations[file])
    # Unknown: use median of known or default estimate
    if durations:
        vals = sorted(durations.values())
        mid = len(vals) // 2
        if len(vals) % 2 == 1:
            return float(vals[mid])
        else:
            return float((vals[mid - 1] + vals[mid]) / 2.0)
    return DEFAULT_ESTIMATE


def balance(files: List[str], durations: Dict[str, float], shard_total: int) -> List[List[str]]:
    # Greedy longest-processing-time first bin packing
    estimated = [(f, estimate_duration(f, durations)) for f in files]
    estimated.sort(key=lambda x: x[1], reverse=True)

    buckets: List[List[str]] = [[] for _ in range(shard_total)]
    bucket_sums = [0.0 for _ in range(shard_total)]

    for f, t in estimated:
        # pick shard with smallest current sum
        i = min(range(shard_total), key=lambda k: bucket_sums[k])
        buckets[i].append(f)
        bucket_sums[i] += t
    return buckets


def main():
    parser = argparse.ArgumentParser(description="Auto-split pytest test files into shards based on historic durations.")
    parser.add_argument("--shard-index", type=int, help="Index of the current shard (0-based).", default=None)
    parser.add_argument("--shard-total", type=int, help="Total number of shards.", default=None)
    parser.add_argument("--test-glob", type=str, help="Glob to discover test files.", default=DEFAULT_GLOB)
    parser.add_argument("--durations-file", type=str, help="Path to durations JSON file.", default=str(DURATIONS_PATH))
    parser.add_argument("--output", type=str, help="Write assigned test files (newline-separated) to this file. If omitted, prints to stdout.")

    args = parser.parse_args()

    env_idx, env_total = read_env_shard_config()
    shard_index = args.shard_index if args.shard_index is not None else env_idx
    shard_total = args.shard_total if args.shard_total is not None else env_total

    if shard_index < 0 or shard_total <= 0 or shard_index >= shard_total:
        print(f"Invalid shard configuration: index={shard_index}, total={shard_total}", file=sys.stderr)
        shard_index, shard_total = 0, 1

    durations = load_durations(Path(args.durations_file))
    files = discover_tests(args.test_glob)

    if not files:
        assigned: List[str] = []
    else:
        shards = balance(files, durations, shard_total)
        assigned = shards[shard_index]

    output_text = "\n".join(assigned)
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_text, encoding="utf-8")
    else:
        print(output_text)


if __name__ == "__main__":
    main()

