import hashlib
import json
import math
import os
import platform
import random
import re
import socket
import sys
import tempfile
import threading
import time
from datetime import datetime
from typing import Any, Dict, Optional

VERSION = "0.1.0"

_lock = threading.Lock()
BASELINE: Dict[str, Any] = {}


def _env_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    val = os.environ.get(name)
    if val is None:
        return default
    try:
        return int(val)
    except Exception:
        return default


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _bench_time_budget_ms(total_ms: int, count: int) -> int:
    if count <= 0:
        return max(50, min(200, total_ms))
    per = max(10, min(100, int(total_ms / count)))
    return per


# Micro-benchmarks

def benchmark_cpu_math(duration_ms: int) -> Dict[str, Any]:
    start = time.perf_counter()
    deadline = start + (duration_ms / 1000.0)
    i = 0
    x = 1.123456789
    y = 2.987654321
    # Tight FP loop
    while True:
        x = x * y + 1.23456789
        y = y * 0.99991 + 0.12345
        x = x - math.sin(y)
        i += 1
        if i % 1024 == 0:
            if time.perf_counter() >= deadline:
                break
    elapsed = max(1e-9, time.perf_counter() - start)
    ops_per_sec = i / elapsed
    return {"cpu_math_ops_per_sec": ops_per_sec, "_elapsed_ms": elapsed * 1000.0}


def benchmark_json(duration_ms: int) -> Dict[str, Any]:
    payload = {
        "a": list(range(16)),
        "b": "x" * 128,
        "c": 123456789,
        "d": 3.14159,
        "e": {"nested": True, "values": [1, 2, 3, 4]},
    }
    start = time.perf_counter()
    deadline = start + (duration_ms / 1000.0)
    i = 0
    dumps = json.dumps
    loads = json.loads
    while True:
        s = dumps(payload)
        obj = loads(s)
        if obj.get("c") != 123456789:
            # ensure result is used
            raise RuntimeError("JSON roundtrip validation failed")
        i += 1
        if i % 128 == 0:
            if time.perf_counter() >= deadline:
                break
    elapsed = max(1e-9, time.perf_counter() - start)
    ops_per_sec = i / elapsed
    return {"json_roundtrip_ops_per_sec": ops_per_sec, "_elapsed_ms": elapsed * 1000.0}


def benchmark_regex(duration_ms: int) -> Dict[str, Any]:
    pat = re.compile(r"\b[a-z]{3,8}ing\b", re.IGNORECASE)
    text = (
        "This string is containing various interesting and compelling words, "
        "including running, walking, reading, and coding."
    )
    start = time.perf_counter()
    deadline = start + (duration_ms / 1000.0)
    i = 0
    while True:
        m = pat.findall(text)
        if not m:
            raise RuntimeError("Regex failed to find matches")
        i += 1
        if i % 1024 == 0:
            if time.perf_counter() >= deadline:
                break
    elapsed = max(1e-9, time.perf_counter() - start)
    ops_per_sec = i / elapsed
    return {"regex_ops_per_sec": ops_per_sec, "_elapsed_ms": elapsed * 1000.0}


def benchmark_hash(duration_ms: int) -> Dict[str, Any]:
    buf = b"x" * (64 * 1024)  # 64 KB
    start = time.perf_counter()
    deadline = start + (duration_ms / 1000.0)
    bytes_processed = 0
    h = hashlib.sha256
    while True:
        hashlib.sha256(buf).digest()
        bytes_processed += len(buf)
        if bytes_processed % (64 * 1024 * 16) == 0:  # check occasionally
            if time.perf_counter() >= deadline:
                break
    elapsed = max(1e-9, time.perf_counter() - start)
    mb_per_sec = (bytes_processed / 1_000_000.0) / elapsed
    return {"hash_sha256_mb_per_sec": mb_per_sec, "_elapsed_ms": elapsed * 1000.0}


def benchmark_mem_alloc(duration_ms: int) -> Dict[str, Any]:
    start = time.perf_counter()
    deadline = start + (duration_ms / 1000.0)
    ring_size = 1024
    ring = [None] * ring_size
    idx = 0
    i = 0
    chunk = b"y" * 4096
    while True:
        ring[idx % ring_size] = bytes(chunk)  # allocate new object
        idx += 1
        i += 1
        if i % 4096 == 0:
            if time.perf_counter() >= deadline:
                break
    elapsed = max(1e-9, time.perf_counter() - start)
    ops_per_sec = i / elapsed
    return {"mem_alloc_ops_per_sec": ops_per_sec, "_elapsed_ms": elapsed * 1000.0}


def benchmark_rand(duration_ms: int) -> Dict[str, Any]:
    start = time.perf_counter()
    deadline = start + (duration_ms / 1000.0)
    bytes_total = 0
    chunk_size = 32 * 1024
    while True:
        os.urandom(chunk_size)
        bytes_total += chunk_size
        if bytes_total % (chunk_size * 32) == 0:
            if time.perf_counter() >= deadline:
                break
    elapsed = max(1e-9, time.perf_counter() - start)
    mb_per_sec = (bytes_total / 1_000_000.0) / elapsed
    return {"rand_urandom_mb_per_sec": mb_per_sec, "_elapsed_ms": elapsed * 1000.0}


def benchmark_file_write(duration_ms: int) -> Dict[str, Any]:
    temp_path = None
    f = None
    try:
        tf = tempfile.NamedTemporaryFile(delete=False)
        temp_path = tf.name
        tf.close()
        f = open(temp_path, "wb", buffering=1024 * 1024)
        start = time.perf_counter()
        deadline = start + (duration_ms / 1000.0)
        chunk = b"z" * (128 * 1024)
        bytes_written = 0
        while True:
            f.write(chunk)
            bytes_written += len(chunk)
            if bytes_written % (128 * 1024 * 16) == 0:
                if time.perf_counter() >= deadline:
                    break
        f.flush()
        elapsed = max(1e-9, time.perf_counter() - start)
        mb_per_sec = (bytes_written / 1_000_000.0) / elapsed
        return {
            "file_write_mb_per_sec": mb_per_sec,
            "_elapsed_ms": elapsed * 1000.0,
            "_temp_path": temp_path,
            "_bytes_written": bytes_written,
        }
    except Exception as e:
        return {
            "file_write_mb_per_sec": None,
            "_elapsed_ms": 0.0,
            "_error": str(e),
            "_temp_path": temp_path,
        }
    finally:
        try:
            if f is not None:
                f.close()
        except Exception:
            pass


def benchmark_file_read(duration_ms: int, path: str) -> Dict[str, Any]:
    if not path or not os.path.exists(path):
        return {"file_read_mb_per_sec": None, "_elapsed_ms": 0.0, "_error": "no_file"}
    try:
        start = time.perf_counter()
        deadline = start + (duration_ms / 1000.0)
        bytes_read = 0
        chunk_size = 128 * 1024
        while time.perf_counter() < deadline:
            with open(path, "rb", buffering=1024 * 1024) as f:
                while True:
                    b = f.read(chunk_size)
                    if not b:
                        break
                    bytes_read += len(b)
                    # Check deadline periodically
                    if bytes_read % (chunk_size * 32) == 0:
                        if time.perf_counter() >= deadline:
                            break
        elapsed = max(1e-9, time.perf_counter() - start)
        mb_per_sec = (bytes_read / 1_000_000.0) / elapsed
        return {"file_read_mb_per_sec": mb_per_sec, "_elapsed_ms": elapsed * 1000.0}
    except Exception as e:
        return {"file_read_mb_per_sec": None, "_elapsed_ms": 0.0, "_error": str(e)}
    finally:
        try:
            os.remove(path)
        except Exception:
            pass


# Orchestrator

def _collect_env() -> Dict[str, Any]:
    return {
        "PERF_BASELINE_DISABLE": os.environ.get("PERF_BASELINE_DISABLE"),
        "PERF_BASELINE_TOTAL_MS": os.environ.get("PERF_BASELINE_TOTAL_MS"),
        "PERF_BASELINE_IO": os.environ.get("PERF_BASELINE_IO"),
    }


def _run_all(max_total_ms: Optional[int] = None) -> Dict[str, Any]:
    total_ms = int(max_total_ms) if max_total_ms is not None else _env_int("PERF_BASELINE_TOTAL_MS", 500)
    io_enabled = _env_bool("PERF_BASELINE_IO", True)
    
    benchmarks = [
        ("cpu_math", benchmark_cpu_math),
        ("json", benchmark_json),
        ("regex", benchmark_regex),
        ("hash", benchmark_hash),
        ("mem_alloc", benchmark_mem_alloc),
        ("rand", benchmark_rand),
    ]
    
    count = len(benchmarks)
    if io_enabled:
        count += 2  # file_write and file_read
    
    per_bench_ms = _bench_time_budget_ms(total_ms, count)
    
    results = {}
    
    for name, func in benchmarks:
        try:
            result = func(per_bench_ms)
            results.update(result)
        except Exception as e:
            results[f"{name}_error"] = str(e)
    
    # File I/O benchmarks
    if io_enabled:
        try:
            write_result = benchmark_file_write(per_bench_ms)
            temp_path = write_result.pop("_temp_path", None)
            results.update(write_result)
            
            if temp_path:
                read_result = benchmark_file_read(per_bench_ms, temp_path)
                results.update(read_result)
        except Exception as e:
            results["file_io_error"] = str(e)
    
    return results


def get_baseline() -> Dict[str, Any]:
    """Return the cached baseline, or run benchmarks if not yet cached."""
    global BASELINE
    with _lock:
        if not BASELINE:
            BASELINE = _initialize_baseline()
        return dict(BASELINE)


def rerun(total_ms: Optional[int] = None) -> Dict[str, Any]:
    """Re-run benchmarks and update the cached baseline."""
    global BASELINE
    with _lock:
        BASELINE = _initialize_baseline(total_ms=total_ms)
        return dict(BASELINE)


def _initialize_baseline(total_ms: Optional[int] = None) -> Dict[str, Any]:
    """Initialize or re-initialize the baseline by running benchmarks."""
    if _env_bool("PERF_BASELINE_DISABLE", False):
        return {
            "version": VERSION,
            "generated_at": _now_iso(),
            "disabled": True,
            "env": _collect_env(),
        }
    
    bench_results = _run_all(max_total_ms=total_ms)
    
    return {
        "version": VERSION,
        "generated_at": _now_iso(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
        },
        "benchmarks": bench_results,
        "env": _collect_env(),
    }


# Run benchmarks on import (unless disabled)
if not _env_bool("PERF_BASELINE_DISABLE", False):
    BASELINE = _initialize_baseline()
