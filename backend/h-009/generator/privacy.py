from typing import Dict, List, Optional

import numpy as np
import pandas as pd


def enforce_uniqueness(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    if not cols:
        return df
    # Resolve duplicates by appending a small suffix counter
    group = df.groupby(cols, dropna=False).cumcount()
    for idx, c in enumerate(cols):
        # Only modify the last column to keep composite key meaningful
        if idx == len(cols) - 1:
            suffix = group.astype(str).where(group > 0, other="")
            df[c] = df[c].astype(str) + suffix.replace({"0": ""})
    return df


def _generalize_numeric(series: pd.Series, min_k: int, max_bins: int = 10) -> pd.Series:
    n = len(series)
    bins = max_bins
    # Iteratively reduce bins until bin sizes satisfy k or 1 bin left
    while bins >= 1:
        try:
            labels = pd.qcut(series.astype(float), q=bins, duplicates="drop")
        except Exception:
            # Fallback to single bin
            labels = pd.Series([pd.Interval(left=float(series.min()), right=float(series.max()), closed="right")] * n, index=series.index)
        counts = labels.value_counts()
        if counts.min() >= min_k or bins == 1:
            return labels.astype(str)
        bins -= 1
    return series.astype(str)


def _generalize_categorical(series: pd.Series, min_k: int) -> pd.Series:
    counts = series.value_counts(dropna=False)
    rare = counts[counts < min_k].index
    gen = series.astype(object).copy()
    gen[series.isin(rare)] = "Other"
    return gen.astype(str)


def enforce_k_anonymity(df: pd.DataFrame, qi_cols: List[str], k: int) -> pd.DataFrame:
    if not qi_cols or k is None or k <= 1:
        return df
    work = df.copy()

    # Generalize columns iteratively
    for col in qi_cols:
        s = work[col]
        if pd.api.types.is_numeric_dtype(s):
            work[col] = _generalize_numeric(s, min_k=k)
        else:
            work[col] = _generalize_categorical(s, min_k=k)

    # Check groups; if still violating k, coarsen further by collapsing rare combos to 'Other'
    grp_sizes = work.groupby(qi_cols, dropna=False).size()
    violating_keys = grp_sizes[grp_sizes < k].index
    if len(violating_keys) > 0:
        # Replace violating rows' QIs with a global bucket label
        mask = work.set_index(qi_cols).index.isin(violating_keys)
        for col in qi_cols:
            work.loc[mask, col] = f"GEN_{col}_OTHER"

    return work


def apply_dp_noise(df: pd.DataFrame, columns: List[str], epsilon: float, sensitivity: Optional[float] = 1.0) -> pd.DataFrame:
    if epsilon is None or epsilon <= 0:
        return df
    sens = float(sensitivity if sensitivity is not None else 1.0)
    scale = sens / float(epsilon)
    noisy = df.copy()
    for col in columns or []:
        if col in noisy.columns and pd.api.types.is_numeric_dtype(noisy[col]):
            noise = np.random.laplace(loc=0.0, scale=scale, size=len(noisy))
            noisy[col] = noisy[col].astype(float) + noise
    return noisy


def drop_columns(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    to_drop = [c for c in cols or [] if c in df.columns]
    return df.drop(columns=to_drop) if to_drop else df


def apply_privacy_rules(df: pd.DataFrame, privacy: Dict, schema: List[Dict]) -> pd.DataFrame:
    if not isinstance(privacy, dict):
        return df
    out = df.copy()

    # Drop sensitive columns if requested
    out = drop_columns(out, (privacy.get("drop_columns") or []))

    # Enforce dataset-level uniqueness on key columns
    uniq_cols = privacy.get("uniqueness") or []
    if uniq_cols:
        missing = [c for c in uniq_cols if c not in out.columns]
        if missing:
            raise ValueError(f"Uniqueness columns not found: {missing}")
        out = enforce_uniqueness(out, uniq_cols)

    # k-anonymity via generalization
    kanon = privacy.get("k_anonymity") or {}
    qi_cols = kanon.get("quasi_identifiers") or []
    k = kanon.get("k", 0)
    if qi_cols and k and k > 1:
        missing_qi = [c for c in qi_cols if c not in out.columns]
        if missing_qi:
            raise ValueError(f"k-anonymity QI columns not found: {missing_qi}")
        out = enforce_k_anonymity(out, qi_cols=qi_cols, k=int(k))

    # Differential privacy noise on numeric columns
    dp = privacy.get("dp_noise") or {}
    dp_cols = dp.get("columns") or []
    epsilon = dp.get("epsilon")
    sensitivity = dp.get("sensitivity", 1.0)
    if dp_cols and epsilon is not None:
        missing_dp = [c for c in dp_cols if c not in out.columns]
        if missing_dp:
            raise ValueError(f"DP columns not found: {missing_dp}")
        out = apply_dp_noise(out, dp_cols, float(epsilon), sensitivity)

    return out

