import math
import os
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from dateutil import parser as date_parser


BOOLEAN_TRUE = {"true", "t", "yes", "y", "1"}
BOOLEAN_FALSE = {"false", "f", "no", "n", "0"}


def _coerce_bool(val: Any) -> Optional[bool]:
    if val is None:
        return None
    s = str(val).strip().lower()
    if s in BOOLEAN_TRUE:
        return True
    if s in BOOLEAN_FALSE:
        return False
    return None


def _infer_type(series: pd.Series) -> Dict[str, Any]:
    s = series.dropna()
    total = len(s)
    if total == 0:
        return {"inferred_type": "string", "consistency": 1.0, "converted": series}

    # Try boolean
    bool_vals = s.apply(_coerce_bool)
    bool_matches = bool_vals.notna().sum()
    bool_ratio = bool_matches / total if total else 0.0

    # Try numeric (float/int)
    num_vals = pd.to_numeric(s, errors="coerce")
    num_matches = num_vals.notna().sum()
    num_ratio = num_matches / total if total else 0.0

    # Try datetime
    try:
        dt_vals = pd.to_datetime(s, errors="coerce", infer_datetime_format=True, utc=True)
        dt_matches = dt_vals.notna().sum()
        dt_ratio = dt_matches / total if total else 0.0
    except Exception:
        dt_vals = pd.Series([pd.NaT] * len(s), index=s.index)
        dt_ratio = 0.0

    # Choose the best ratio over a threshold
    candidates = [
        ("boolean", bool_ratio, bool_vals),
        ("number", num_ratio, num_vals),
        ("datetime", dt_ratio, dt_vals),
    ]
    candidates.sort(key=lambda x: x[1], reverse=True)

    best_type, best_ratio, converted = candidates[0]
    threshold = 0.8
    if best_ratio >= threshold:
        # If number, refine to integer if all non-null are close to ints
        if best_type == "number":
            nonnull = converted.dropna()
            if not nonnull.empty:
                # Check if all close to int
                diffs = np.abs(nonnull - np.round(nonnull))
                if (diffs < 1e-9).all():
                    best_type = "integer"
        # Rebuild a full-length converted series aligned with original index
        full_converted = pd.Series([np.nan] * len(series), index=series.index)
        full_converted.loc[s.index] = converted
        return {"inferred_type": best_type, "consistency": float(best_ratio), "converted": full_converted}

    # Fallback to string
    return {"inferred_type": "string", "consistency": float(1.0), "converted": series.astype(str)}


def _numeric_summary(series: pd.Series) -> Dict[str, Any]:
    nonnull = series.dropna()
    if nonnull.empty:
        return {"min": None, "max": None, "mean": None, "std": None}
    return {
        "min": float(np.min(nonnull)),
        "max": float(np.max(nonnull)),
        "mean": float(np.mean(nonnull)),
        "std": float(np.std(nonnull, ddof=0)),
    }


def _datetime_summary(series: pd.Series) -> Dict[str, Any]:
    nonnull = series.dropna()
    if nonnull.empty:
        return {"min": None, "max": None}
    # Ensure pandas Timestamp -> ISO string
    return {
        "min": pd.to_datetime(nonnull.min()).isoformat(),
        "max": pd.to_datetime(nonnull.max()).isoformat(),
    }


def _string_summary(series: pd.Series) -> Dict[str, Any]:
    nonnull = series.dropna().astype(str)
    if nonnull.empty:
        return {"min": None, "max": None, "avg_length": None, "min_length": None, "max_length": None}
    lengths = nonnull.str.len()
    return {
        "min": min(nonnull),
        "max": max(nonnull),
        "avg_length": float(lengths.mean()),
        "min_length": int(lengths.min()),
        "max_length": int(lengths.max()),
    }


def _example_values(series: pd.Series, k: int = 5) -> List[Any]:
    try:
        return series.dropna().drop_duplicates().astype(str).head(k).tolist()
    except Exception:
        return []


def _json_safe(val):
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        x = float(val)
        if math.isfinite(x):
            return x
        return None
    if isinstance(val, (np.bool_,)):
        return bool(val)
    if isinstance(val, (pd.Timestamp,)):
        return val.isoformat()
    if isinstance(val, (pd.Timedelta,)):
        return str(val)
    return val


def _dict_json_safe(d: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out[k] = _dict_json_safe(v)
        elif isinstance(v, list):
            out[k] = [_dict_json_safe(i) if isinstance(i, dict) else _json_safe(i) for i in v]
        else:
            out[k] = _json_safe(v)
    return out


def analyze_csv(file_path: str, sample_size: int = 10, read_rows_limit: Optional[int] = None) -> Dict[str, Any]:
    if not os.path.exists(file_path):
        raise FileNotFoundError(file_path)

    # Read entire file or limited rows as strings to avoid dtype inference surprises
    read_kwargs = dict(low_memory=False)
    if read_rows_limit is not None:
        df = pd.read_csv(file_path, nrows=read_rows_limit, **read_kwargs)
    else:
        df = pd.read_csv(file_path, **read_kwargs)

    # Keep original for duplicate checks
    df_original = df.copy()

    row_count = int(len(df))
    col_count = int(len(df.columns))

    schema = []
    column_metrics = {}

    for col in df.columns:
        col_series = df[col]
        null_count = int(col_series.isna().sum())
        non_null_count = int(row_count - null_count)
        completeness = float(non_null_count / row_count) if row_count else 1.0

        infer = _infer_type(col_series)
        inferred_type = infer["inferred_type"]
        consistency = float(infer["consistency"])
        converted = infer["converted"]

        distinct_non_null = int(col_series.dropna().nunique())
        uniqueness = float(distinct_non_null / non_null_count) if non_null_count else 1.0

        # Summaries based on type
        if inferred_type in ("number", "integer"):
            summary = _numeric_summary(pd.to_numeric(converted, errors="coerce"))
        elif inferred_type == "datetime":
            summary = _datetime_summary(pd.to_datetime(converted, errors="coerce", utc=True))
        elif inferred_type == "boolean":
            # Convert to boolean series
            bool_series = col_series.dropna().apply(_coerce_bool)
            true_count = int(pd.Series(bool_series, index=col_series.dropna().index).fillna(False).sum())
            false_count = int(non_null_count - true_count)
            summary = {"true": true_count, "false": false_count}
        else:
            summary = _string_summary(col_series.astype(str))

        examples = _example_values(col_series, k=5)

        schema.append({
            "name": str(col),
            "inferred_type": inferred_type,
            "nullable": null_count > 0,
        })

        column_metrics[col] = {
            "null_count": null_count,
            "non_null_count": non_null_count,
            "completeness": completeness,
            "distinct_count": distinct_non_null,
            "uniqueness": uniqueness,
            "type_consistency": consistency,
            "summary": summary,
            "example_values": examples,
        }

    # Dataset-level metrics
    duplicate_rows = int(df_original.duplicated().sum())
    missing_cells = int(df_original.isna().sum().sum())
    total_cells = int(row_count * col_count)
    dataset_completeness = float(1.0 - (missing_cells / total_cells)) if total_cells else 1.0

    # Sample rows for quick preview
    sample_rows = df.head(sample_size).fillna(None).to_dict(orient="records")

    quality_metrics = {
        "row_count": row_count,
        "col_count": col_count,
        "duplicate_rows": duplicate_rows,
        "missing_cells": missing_cells,
        "total_cells": total_cells,
        "dataset_completeness": dataset_completeness,
        "columns": column_metrics,
    }

    result = {
        "row_count": row_count,
        "col_count": col_count,
        "schema": _dict_json_safe({"fields": schema}),
        "quality_metrics": _dict_json_safe(quality_metrics),
        "sample_rows": sample_rows,
    }
    return result


def preview_csv(file_path: str, limit: int = 50) -> Dict[str, Any]:
    df = pd.read_csv(file_path, nrows=limit, low_memory=False)
    rows = df.fillna(None).to_dict(orient="records")
    return {"columns": [str(c) for c in df.columns], "rows": rows}

