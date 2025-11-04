import os
import io
import time
import random
import torch
import numpy as np


def set_seed(seed: int = 42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def save_package(path: str, package: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    torch.save(package, path)


def load_package(path: str) -> dict:
    return torch.load(path, map_location="cpu")


def file_size_mb(path: str) -> float:
    return os.path.getsize(path) / (1024 * 1024)


def count_parameters(model: torch.nn.Module) -> int:
    return sum(p.numel() for p in model.parameters())


def timeit_sync(func, *args, repeat: int = 10, warmup: int = 2, **kwargs):
    times = []
    for _ in range(warmup):
        func(*args, **kwargs)
    for _ in range(repeat):
        t0 = time.perf_counter()
        func(*args, **kwargs)
        t1 = time.perf_counter()
        times.append(t1 - t0)
    return {
        "p50_ms": np.percentile(times, 50) * 1000,
        "p90_ms": np.percentile(times, 90) * 1000,
        "mean_ms": float(np.mean(times) * 1000),
    }

