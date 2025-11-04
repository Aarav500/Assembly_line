import re
from typing import Dict, Tuple, Set, Any
import pandas as pd


DTYPE_CASTERS = {
    "int": lambda s: pd.to_numeric(s, errors="coerce").astype("Int64"),
    "int64": lambda s: pd.to_numeric(s, errors="coerce").astype("Int64"),
    "float": lambda s: pd.to_numeric(s, errors="coerce").astype("float64"),
    "float64": lambda s: pd.to_numeric(s, errors="coerce").astype("float64"),
    "str": lambda s: s.astype("string"),
    "string": lambda s: s.astype("string"),
    "datetime": lambda s: pd.to_datetime(s, errors="coerce"),
}


def coerce_dtypes(df: pd.DataFrame, dtypes: Dict[str, str]) -> pd.DataFrame:
    df = df.copy()
    for col, dtype in dtypes.items():
        if col in df.columns:
            caster = DTYPE_CASTERS.get(dtype)
            if caster:
                try:
                    df[col] = caster(df[col])
                except Exception:
                    # leave as-is on failure, will be caught in validation
                    pass
    return df


def validate_chunk(df: pd.DataFrame, schema: Dict[str, Any], unique_state: Dict[str, Set[Any]]) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Set[Any]]]:
    required = set(schema.get("required_columns", []))
    dtypes = schema.get("dtypes", {})
    constraints = schema.get("constraints", {})
    unique_cols = schema.get("unique", [])

    # Coerce types first
    if dtypes:
        df = coerce_dtypes(df, dtypes)

    errors = []

    # Missing required columns (file-level)
    missing_cols = [c for c in required if c not in df.columns]
    if missing_cols:
        # mark entire chunk rows as error
        err_df = df.copy()
        err_df["__errors"] = f"Missing required columns: {','.join(missing_cols)}"
        return pd.DataFrame(columns=df.columns), err_df, unique_state

    # Row-level validation
    error_messages = pd.Series(["" for _ in range(len(df))], index=df.index, dtype="object")

    # Required not-null
    for col in required:
        mask = df[col].isna()
        if mask.any():
            error_messages.loc[mask] = (error_messages.loc[mask] + ("; " if error_messages.loc[mask].astype(bool).any() else "") + f"{col} is required")

    # Numeric min/max and regex
    for col, rules in constraints.items():
        if col not in df.columns:
            continue
        series = df[col]
        if series.dtype.kind in {"i", "u", "f", "M"} or (str(series.dtype).startswith("Int") or str(series.dtype).startswith("Float")):
            if "min" in rules:
                mask = series < rules["min"]
                if mask.any():
                    error_messages.loc[mask] = (error_messages.loc[mask] + ("; " if error_messages.loc[mask].astype(bool).any() else "") + f"{col} < {rules['min']}")
            if "max" in rules:
                mask = series > rules["max"]
                if mask.any():
                    error_messages.loc[mask] = (error_messages.loc[mask] + ("; " if error_messages.loc[mask].astype(bool).any() else "") + f"{col} > {rules['max']}")
        if "regex" in rules:
            try:
                pattern = re.compile(rules["regex"])  # type: ignore
                mask = ~df[col].astype(str).str.match(pattern)
                mask = mask & df[col].notna()
                if mask.any():
                    error_messages.loc[mask] = (error_messages.loc[mask] + ("; " if error_messages.loc[mask].astype(bool).any() else "") + f"{col} regex mismatch")
            except re.error:
                pass

    # Uniqueness
    for col in unique_cols:
        if col not in df.columns:
            continue
        seen = unique_state.setdefault(col, set())
        duplicated_within = df[col].duplicated(keep=False)
        if duplicated_within.any():
            mask = duplicated_within
            error_messages.loc[mask] = (error_messages.loc[mask] + ("; " if error_messages.loc[mask].astype(bool).any() else "") + f"{col} duplicate in chunk")
        # across chunks
        mask_dup_across = df[col].isin(seen)
        if mask_dup_across.any():
            error_messages.loc[mask_dup_across] = (error_messages.loc[mask_dup_across] + ("; " if error_messages.loc[mask_dup_across].astype(bool).any() else "") + f"{col} duplicate across chunks")
        # update seen with non-null values
        new_values = df.loc[df[col].notna(), col].tolist()
        for v in new_values:
            seen.add(v)
        unique_state[col] = seen

    invalid_mask = error_messages.astype(bool)
    errors_df = df.loc[invalid_mask].copy()
    if not errors_df.empty:
        errors_df["__errors"] = error_messages.loc[invalid_mask].values

    clean_df = df.loc[~invalid_mask].copy()

    return clean_df, errors_df, unique_state

