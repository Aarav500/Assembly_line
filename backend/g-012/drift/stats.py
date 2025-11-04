from typing import List, Tuple, Dict, Any
import math
import numpy as np
from scipy.stats import chisquare


EPS = 1e-8


def is_number(x) -> bool:
    try:
        return x is not None and not (isinstance(x, bool)) and not (isinstance(x, str)) and math.isfinite(float(x))
    except Exception:
        return False


def compute_bin_edges(values: List[float], num_bins: int) -> List[float]:
    arr = np.array(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return [0.0, 1.0]
    if np.all(arr == arr[0]):
        v = float(arr[0])
        return [v - 0.5 if v != 0 else -0.5, v + 0.5 if v != 0 else 0.5]
    # quantile-based edges
    qs = np.linspace(0.0, 1.0, num_bins + 1)
    edges = np.quantile(arr, qs)
    # Ensure strictly increasing
    edges = np.unique(edges)
    if edges.size < 2:
        mn, mx = float(arr.min()), float(arr.max())
        if mn == mx:
            return [mn - 0.5, mx + 0.5]
        edges = np.linspace(mn, mx, num_bins + 1)
    return edges.tolist()


def histogram_proportions(values: List[float], bin_edges: List[float]) -> List[float]:
    if not values:
        return [0.0 for _ in range(max(1, len(bin_edges) - 1))]
    arr = np.array([float(v) for v in values if is_number(v)], dtype=float)
    if arr.size == 0:
        return [0.0 for _ in range(max(1, len(bin_edges) - 1))]
    counts, _ = np.histogram(arr, bins=np.array(bin_edges, dtype=float))
    total = float(counts.sum())
    if total <= 0:
        return [0.0 for _ in counts]
    return (counts / total).astype(float).tolist()


def psi(expected: List[float], actual: List[float]) -> float:
    b = np.array(expected, dtype=float)
    e = np.array(actual, dtype=float)
    if b.size != e.size:
        # pad shorter with zeros
        n = max(b.size, e.size)
        b = np.pad(b, (0, n - b.size), constant_values=0.0)
        e = np.pad(e, (0, n - e.size), constant_values=0.0)
    b = np.clip(b, EPS, None)
    e = np.clip(e, EPS, None)
    return float(np.sum((e - b) * np.log(e / b)))


def categorical_proportions(values: List[Any], categories: List[str]) -> List[float]:
    if not values:
        return [0.0 for _ in categories]
    counts = {c: 0 for c in categories}
    other_key = None
    for c in categories:
        if c == '__OTHER__':
            other_key = c
            break
    for v in values:
        key = str(v)
        if key in counts:
            counts[key] += 1
        elif other_key is not None:
            counts[other_key] += 1
        else:
            # unseen category without OTHER bucket; skip
            pass
    total = sum(counts.values())
    if total <= 0:
        return [0.0 for _ in categories]
    return [counts[c] / total for c in categories]


def chi2_pvalue(observed_counts: List[float], expected_proportions: List[float]) -> float:
    obs = np.array(observed_counts, dtype=float)
    exp_prop = np.array(expected_proportions, dtype=float)
    exp_prop = exp_prop / max(exp_prop.sum(), EPS)
    exp_counts = exp_prop * max(obs.sum(), 1.0)
    # Avoid zero expected counts
    exp_counts = np.clip(exp_counts, EPS, None)
    stat, p = chisquare(f_obs=obs, f_exp=exp_counts)
    return float(p)


def proportions_from_counts(counts: List[int]) -> List[float]:
    total = float(sum(counts))
    if total <= 0:
        return [0.0 for _ in counts]
    return [c / total for c in counts]

