import io
from typing import Tuple, Dict, Any

import pandas as pd


def serialize_dataframe(df: pd.DataFrame, fmt: str = 'csv', options: Dict[str, Any] | None = None) -> Tuple[bytes, str, str]:
    options = options or {}
    fmt = fmt.lower()

    if fmt == 'csv':
        csv_opts = {k: v for k, v in options.items() if k in {'sep', 'encoding', 'header', 'index', 'quoting'} }
        csv_opts.setdefault('index', False)
        encoding = csv_opts.pop('encoding', 'utf-8')
        data = df.to_csv(**csv_opts).encode(encoding)
        return data, 'text/csv', 'csv'

    if fmt == 'parquet':
        pq_opts = {k: v for k, v in options.items() if k in {'compression', 'engine'} }
        pq_opts.setdefault('engine', 'pyarrow')
        buf = io.BytesIO()
        df.to_parquet(buf, index=False, **pq_opts)
        return buf.getvalue(), 'application/vnd.apache.parquet', 'parquet'

    raise ValueError(f"Unsupported format: {fmt}")

