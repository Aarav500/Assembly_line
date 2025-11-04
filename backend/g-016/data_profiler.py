import os
import json
from datetime import datetime
from typing import Dict, Any

import numpy as np
import pandas as pd


def _now_iso():
    return datetime.utcnow().isoformat() + 'Z'


def load_profile_cached(path: str):
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def compute_and_cache_profile(name: str, dataset_path: str, profile_path: str) -> Dict[str, Any]:
    df = pd.read_csv(dataset_path, low_memory=False)
    profile = compute_profile(df)
    profile['dataset_name'] = name
    profile['generated_at'] = _now_iso()
    with open(profile_path, 'w', encoding='utf-8') as f:
        json.dump(profile, f, ensure_ascii=False)
    return profile


def compute_profile(df: pd.DataFrame) -> Dict[str, Any]:
    n_rows, n_cols = df.shape
    memory_bytes = int(df.memory_usage(deep=True).sum())
    duplicate_rows = int(df.duplicated().sum())
    missing_total = int(df.isna().sum().sum())

    columns_profile = {}

    # Determine column types and stats
    for col in df.columns:
        s = df[col]
        col_profile = profile_column(s)
        columns_profile[str(col)] = col_profile

    # Correlations for numeric
    num_df = df.select_dtypes(include=[np.number]).copy()
    corr = None
    if num_df.shape[1] >= 2:
        corr_df = num_df.corr(numeric_only=True)
        corr_df = corr_df.fillna(0.0)
        corr = {
            'columns': [str(c) for c in corr_df.columns.tolist()],
            'matrix': corr_df.values.astype(float).round(6).tolist()
        }

    # Missingness by column
    missing_by_col = df.isna().sum()
    missingness = {
        'columns': [str(c) for c in df.columns.tolist()],
        'missing_count': [int(x) for x in missing_by_col.tolist()],
        'missing_pct': [float(mc) / float(n_rows) * 100.0 if n_rows else 0.0 for mc in missing_by_col.tolist()]
    }

    warnings = []
    # High missingness
    for c, pct in zip(missingness['columns'], missingness['missing_pct']):
        if pct > 30.0:
            warnings.append({'type': 'high_missingness', 'column': c, 'missing_pct': round(pct, 2)})
    # High cardinality categoricals
    for c, colp in columns_profile.items():
        if colp.get('inferred_type') == 'categorical' and colp.get('unique_count') and n_rows:
            ur = colp['unique_count'] / max(1, n_rows)
            if ur > 0.8 and colp.get('unique_count') > 50:
                warnings.append({'type': 'high_cardinality', 'column': c, 'unique_ratio': round(ur, 3)})

    basic = {
        'n_rows': int(n_rows),
        'n_cols': int(n_cols),
        'memory_bytes': int(memory_bytes),
        'duplicate_rows': int(duplicate_rows),
        'duplicated_pct': float(duplicate_rows) / float(n_rows) * 100.0 if n_rows else 0.0,
        'missing_total': int(missing_total),
        'missing_pct': float(missing_total) / float(n_rows * max(1, n_cols)) * 100.0 if n_rows and n_cols else 0.0
    }

    return {
        'basic': basic,
        'columns': columns_profile,
        'correlations': corr,
        'missingness': missingness,
        'warnings': warnings
    }


def profile_column(s: pd.Series) -> Dict[str, Any]:
    name = str(s.name)
    total = int(len(s))
    non_null = int(s.notna().sum())
    missing = int(s.isna().sum())
    unique_count = int(s.nunique(dropna=True))

    dtype = str(s.dtype)
    inferred_type = infer_type(s)

    base = {
        'name': name,
        'dtype': dtype,
        'inferred_type': inferred_type,
        'non_null_count': non_null,
        'missing_count': missing,
        'missing_pct': float(missing) / float(total) * 100.0 if total else 0.0,
        'unique_count': unique_count,
    }

    # Sample values (most frequent)
    try:
        top_vals = s.value_counts(dropna=True).head(5)
        base['sample_values'] = [
            {'value': _to_jsonable(v), 'count': int(c)} for v, c in top_vals.items()
        ]
    except Exception:
        base['sample_values'] = []

    if inferred_type == 'numeric':
        base.update(numeric_stats(s))
    elif inferred_type == 'datetime':
        base.update(datetime_stats(s))
    elif inferred_type == 'boolean':
        base.update(boolean_stats(s))
    elif inferred_type == 'categorical':
        base.update(categorical_stats(s))
    else:  # text
        base.update(text_stats(s))

    return base


def infer_type(s: pd.Series) -> str:
    try:
        if pd.api.types.is_bool_dtype(s):
            return 'boolean'
        if pd.api.types.is_numeric_dtype(s):
            return 'numeric'
        if pd.api.types.is_datetime64_any_dtype(s):
            return 'datetime'
        if pd.api.types.is_categorical_dtype(s):
            return 'categorical'
        # Object: try infer datetime
        if s.dtype == 'object':
            # heuristics
            nunique = s.nunique(dropna=True)
            total = len(s)
            # Try parse few values as datetime
            try:
                sample = s.dropna().astype(str).head(100)
                parsed = pd.to_datetime(sample, errors='coerce', infer_datetime_format=True)
                if parsed.notna().mean() > 0.9:
                    return 'datetime'
            except Exception:
                pass
            if total and nunique <= min(50, int(0.3 * total)):
                return 'categorical'
            return 'text'
    except Exception:
        pass
    return 'text'


def numeric_stats(s: pd.Series) -> Dict[str, Any]:
    x = pd.to_numeric(s, errors='coerce')
    x = x.dropna()
    if len(x) == 0:
        return {
            'stats': None,
            'histogram': None
        }
    q1 = float(x.quantile(0.25))
    q3 = float(x.quantile(0.75))
    iqr = q3 - q1
    low = q1 - 1.5 * iqr
    high = q3 + 1.5 * iqr
    outliers = int(((x < low) | (x > high)).sum())
    zeros = int((x == 0).sum())
    negatives = int((x < 0).sum())
    stats = {
        'min': float(x.min()),
        'q1': q1,
        'median': float(x.median()),
        'mean': float(x.mean()),
        'q3': q3,
        'max': float(x.max()),
        'std': float(x.std(ddof=1)) if len(x) > 1 else 0.0,
        'iqr': float(iqr),
        'zeros_count': zeros,
        'negative_count': negatives,
        'outlier_count': outliers
    }
    # Histogram bins
    bins = int(min(50, max(5, int(np.sqrt(len(x))))))
    counts, edges = np.histogram(x.values, bins=bins)
    histogram = {
        'bin_edges': [float(e) for e in edges.tolist()],
        'counts': [int(c) for c in counts.tolist()]
    }
    return {'stats': stats, 'histogram': histogram}


def categorical_stats(s: pd.Series) -> Dict[str, Any]:
    x = s.astype('object')
    vc = x.value_counts(dropna=True)
    top = vc.head(20)
    top_values = [{'value': _to_jsonable(idx), 'count': int(cnt)} for idx, cnt in top.items()]
    return {
        'top_values': top_values,
        'categories_count': int(vc.shape[0])
    }


def boolean_stats(s: pd.Series) -> Dict[str, Any]:
    x = s.astype('boolean')
    vc = x.value_counts(dropna=False)
    values = []
    for key, cnt in vc.items():
        val = None if pd.isna(key) else bool(key)
        values.append({'value': val, 'count': int(cnt)})
    return {'distribution': values}


def datetime_stats(s: pd.Series) -> Dict[str, Any]:
    try:
        x = pd.to_datetime(s, errors='coerce')
        x = x.dropna()
        if len(x) == 0:
            return {'min': None, 'max': None}
        return {
            'min': x.min().isoformat(),
            'max': x.max().isoformat()
        }
    except Exception:
        return {'min': None, 'max': None}


def text_stats(s: pd.Series) -> Dict[str, Any]:
    x = s.astype('object').dropna()
    if len(x) == 0:
        return {'length': None}
    lens = x.astype(str).str.len()
    return {
        'length': {
            'min': int(lens.min()),
            'q1': float(lens.quantile(0.25)),
            'median': float(lens.median()),
            'mean': float(lens.mean()),
            'q3': float(lens.quantile(0.75)),
            'max': int(lens.max()),
            'std': float(lens.std(ddof=1)) if len(lens) > 1 else 0.0
        }
    }


def _to_jsonable(v):
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if pd.isna(v):
        return None
    return v

