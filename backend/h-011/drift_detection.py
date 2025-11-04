import math
import numpy as np
from collections import Counter, defaultdict
from datetime import datetime

EPS = 1e-12


def iso_now():
    return datetime.utcnow().isoformat() + "Z"


def infer_feature_types(data):
    # data: list of dicts
    types = {}
    if not data:
        return types
    keys = set()
    for r in data[:100]:
        keys.update(r.keys())
    for k in keys:
        vals = []
        for r in data:
            v = r.get(k)
            if v is None:
                continue
            vals.append(v)
            if len(vals) >= 50:
                break
        if not vals:
            # default numeric
            types[k] = "numeric"
            continue
        numeric_like = all(isinstance(v, (int, float)) for v in vals)
        types[k] = "numeric" if numeric_like else "categorical"
    return types


def _numeric_hist(values, edges=None, bins=10):
    vals = np.asarray([v for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))], dtype=float)
    if vals.size == 0:
        if edges is None:
            edges = np.linspace(0.0, 1.0, bins + 1)
        counts = np.zeros(len(edges) - 1, dtype=float)
    else:
        if isinstance(bins, str):
            counts, edges = np.histogram(vals, bins=bins)
        elif edges is not None:
            counts, edges = np.histogram(vals, bins=edges)
        else:
            # Freedman-Diaconis for robust binning
            try:
                counts, edges = np.histogram(vals, bins='fd')
                if len(edges) - 1 > 50:  # cap
                    counts, edges = np.histogram(vals, bins=50)
            except Exception:
                counts, edges = np.histogram(vals, bins=bins)
    probs = counts / (counts.sum() + EPS)
    return counts.astype(float), probs.astype(float), edges.astype(float)


def _categorical_probs(values, categories=None):
    cleaned = []
    for v in values:
        if v is None:
            cleaned.append("__MISSING__")
        else:
            cleaned.append(str(v))
    cnt = Counter(cleaned)
    if categories is None:
        categories = sorted(list(cnt.keys()))
    counts = np.array([cnt.get(cat, 0.0) for cat in categories], dtype=float)
    probs = counts / (counts.sum() + EPS)
    return categories, counts, probs


def _psi(expected_probs, actual_probs):
    e = np.clip(np.asarray(expected_probs, dtype=float), EPS, None)
    a = np.clip(np.asarray(actual_probs, dtype=float), EPS, None)
    return float(np.sum((a - e) * np.log(a / e)))


def _jsd(p, q):
    p = np.clip(np.asarray(p, dtype=float), EPS, None)
    q = np.clip(np.asarray(q, dtype=float), EPS, None)
    m = 0.5 * (p + q)
    kld_pm = np.sum(p * np.log(p / m))
    kld_qm = np.sum(q * np.log(q / m))
    return float(0.5 * (kld_pm + kld_qm) / math.log(2))  # normalized to [0, ~1]


def _ks_from_probs(expected_probs, actual_probs):
    ecdf = np.cumsum(expected_probs)
    acdf = np.cumsum(actual_probs)
    return float(np.max(np.abs(ecdf - acdf)))


def build_baseline_from_data(data, feature_types, bins=None):
    # bins can be int or dict[str, int]
    bins = bins or {}
    baseline = {
        "created_at": iso_now(),
        "feature_types": feature_types,
        "features": {}
    }
    # Organize values per feature
    values_by_feature = defaultdict(list)
    for r in data:
        for k, v in r.items():
            if k in feature_types:
                values_by_feature[k].append(v)
    for feat, ftype in feature_types.items():
        vals = values_by_feature.get(feat, [])
        if ftype == "numeric":
            b = bins.get(feat) if isinstance(bins, dict) else (bins if isinstance(bins, int) else None)
            counts, probs, edges = _numeric_hist(vals, edges=None, bins=b or 10)
            arr = np.array([v for v in vals if v is not None], dtype=float)
            summary = {
                "n": int(arr.size),
                "mean": float(np.mean(arr)) if arr.size else None,
                "std": float(np.std(arr)) if arr.size else None,
                "min": float(np.min(arr)) if arr.size else None,
                "max": float(np.max(arr)) if arr.size else None,
                "q25": float(np.percentile(arr, 25)) if arr.size else None,
                "q50": float(np.percentile(arr, 50)) if arr.size else None,
                "q75": float(np.percentile(arr, 75)) if arr.size else None,
            }
            baseline["features"][feat] = {
                "type": "numeric",
                "bins": edges.tolist(),
                "baseline": {
                    "counts": counts.tolist(),
                    "probs": probs.tolist(),
                    "n": int(arr.size),
                    "summary": summary
                }
            }
        else:
            categories, counts, probs = _categorical_probs(vals, categories=None)
            baseline["features"][feat] = {
                "type": "categorical",
                "categories": categories,
                "baseline": {
                    "counts": counts.tolist(),
                    "probs": probs.tolist(),
                    "n": int(sum(counts)),
                    "summary": {
                        "unique": int(len(categories))
                    }
                }
            }
    return baseline


def compute_drift_for_batch(baseline, data, thresholds):
    # thresholds with sensible defaults
    t = {
        "numeric": {
            "psi": thresholds.get("numeric_psi_threshold", 0.2),
            "ks": thresholds.get("numeric_ks_threshold", 0.1),
            "z_mean": thresholds.get("numeric_zscore_mean_shift_threshold", 3.0)
        },
        "categorical": {
            "psi": thresholds.get("categorical_psi_threshold", 0.2),
            "jsd": thresholds.get("categorical_jsd_threshold", 0.1),
            "new_ratio": thresholds.get("categorical_new_category_ratio_threshold", 0.05)
        }
    }

    metrics_by_feature = {}
    drifted_features = []

    feature_types = baseline.get("feature_types", {})

    # Gather new values per feature
    values_by_feature = defaultdict(list)
    for r in data:
        for k in feature_types.keys():
            values_by_feature[k].append(r.get(k))

    for feat, ftype in feature_types.items():
        base = baseline["features"].get(feat)
        vals = values_by_feature.get(feat, [])
        if ftype == "numeric":
            edges = np.array(base.get("bins"), dtype=float)
            counts, probs, _ = _numeric_hist(vals, edges=edges)
            base_probs = np.array(base["baseline"]["probs"], dtype=float)
            psi = _psi(base_probs, probs)
            ks = _ks_from_probs(base_probs, probs)
            arr = np.array([v for v in vals if v is not None], dtype=float)
            bmean = float(base["baseline"]["summary"].get("mean")) if base["baseline"]["summary"].get("mean") is not None else 0.0
            bstd = float(base["baseline"]["summary"].get("std")) if base["baseline"]["summary"].get("std") not in (None, 0.0) else 1.0
            mean = float(np.mean(arr)) if arr.size else None
            z = abs(((mean if mean is not None else bmean) - bmean) / (bstd + EPS))
            drift_flags = {
                "psi": psi > t["numeric"]["psi"],
                "ks": ks > t["numeric"]["ks"],
                "z_mean": z > t["numeric"]["z_mean"]
            }
            drifted = any(drift_flags.values())
            metrics = {
                "type": "numeric",
                "psi": round(psi, 6),
                "ks": round(ks, 6),
                "mean": round(mean, 6) if mean is not None else None,
                "zscore_mean_shift": round(z, 6),
                "counts": [int(x) for x in counts.tolist()],
                "probs": [float(x) for x in probs.tolist()],
                "drift_flags": drift_flags
            }
            metrics_by_feature[feat] = metrics
            if drifted:
                drifted_features.append(feat)
        else:
            base_cats = base.get("categories", [])
            cats, counts, probs = _categorical_probs(vals, categories=base_cats)
            # Handle unseen categories
            unseen_counts = 0
            all_cats_set = set(base_cats)
            for v in vals:
                key = "__MISSING__" if v is None else str(v)
                if key not in all_cats_set:
                    unseen_counts += 1
            new_ratio = unseen_counts / (len(vals) + EPS)

            base_probs = np.array(base["baseline"]["probs"], dtype=float)
            # Align lengths
            if len(probs) != len(base_probs):
                # Ensure same order as base_cats
                cats, counts, probs = _categorical_probs(vals, categories=base_cats)
            psi = _psi(base_probs, probs)
            jsd = _jsd(base_probs, probs)
            drift_flags = {
                "psi": psi > t["categorical"]["psi"],
                "jsd": jsd > t["categorical"]["jsd"],
                "new_ratio": new_ratio > t["categorical"]["new_ratio"]
            }
            drifted = any(drift_flags.values())
            metrics = {
                "type": "categorical",
                "psi": round(psi, 6),
                "jsd": round(jsd, 6),
                "new_category_ratio": round(new_ratio, 6),
                "categories": cats,
                "counts": [int(x) for x in counts.tolist()],
                "probs": [float(x) for x in probs.tolist()],
                "drift_flags": drift_flags
            }
            metrics_by_feature[feat] = metrics
            if drifted:
                drifted_features.append(feat)

    overall_drift = len(drifted_features) > 0
    return metrics_by_feature, drifted_features, overall_drift

