import os
from typing import Optional, Dict, Any
import pandas as pd

from app.celery_app import celery_app
from app.io_utils import (
    detect_format,
    get_reader,
    get_writer,
    count_rows,
    normalize_output_path,
    ensure_dir,
)
from app.progress import set_progress


@celery_app.task(bind=True)
def export_task(self, input_path: str, output_path: Optional[str] = None, output_format: Optional[str] = None, options: Optional[Dict[str, Any]] = None):
    options = options or {}
    chunk_size = int(options.get("chunk_size", os.getenv("CHUNK_SIZE", 50000)))
    input_format = detect_format(input_path)

    if output_format is None:
        if output_path:
            output_format = detect_format(output_path)
        else:
            raise ValueError("output_format or output_path must be provided")

    if output_path is None:
        base, _ = os.path.splitext(input_path)
        output_path = base + "." + ("jsonl" if output_format == "jsonl" else ("json" if output_format == "json" else ("xlsx" if output_format == "xlsx" else "csv")))

    output_path = normalize_output_path(output_path, output_format)

    total = count_rows(input_path, fmt=input_format)
    processed = 0
    header_written = False

    # Transform options
    select_columns = options.get("columns")  # list
    query = options.get("query")  # pandas query string
    dropna = options.get("dropna", False)
    json_array_pointer = options.get("json_array_pointer", "item")
    json_array_output = bool(options.get("json_array_output", False))

    set_progress(self, 0, total, message="Starting export")

    if output_format == "json" and json_array_output:
        ensure_dir(output_path)
        f = open(output_path, "w", encoding="utf-8")
        f.write("[")
        first_chunk_written = False
    else:
        f = None

    try:
        reader = get_reader(input_path, input_format, chunk_size, json_array_pointer=json_array_pointer)
        writer = None if (output_format == "json" and json_array_output) else get_writer("jsonl" if (output_format == "json" and not json_array_output) else output_format)

        for df in reader:
            if select_columns:
                df = df[[c for c in select_columns if c in df.columns]]
            if query:
                try:
                    df = df.query(query)
                except Exception:
                    pass
            if dropna:
                df = df.dropna()

            if output_format == "json" and json_array_output:
                # Write chunk as part of JSON array
                txt = df.to_json(orient="records", force_ascii=False)
                # strip [ ] to embed into main array
                if txt.startswith("[") and txt.endswith("]"):
                    txt = txt[1:-1]
                if txt.strip():
                    if first_chunk_written:
                        f.write(",")
                    f.write(txt)
                    first_chunk_written = True
            else:
                writer(output_path, df, header_written)
                header_written = True

            processed += len(df)
            set_progress(self, min(processed, total), total, message="Exporting")

        # finalize JSON array
        if output_format == "json" and json_array_output:
            f.write("]")
    finally:
        if f is not None:
            f.close()

    result = {"status": "completed", "input": input_path, "output": output_path, "output_format": output_format, "total_rows": total, "exported_rows": processed}
    set_progress(self, total, total, message="Export completed", extra=result)
    return result

