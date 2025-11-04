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
from app.data_validation import validate_chunk
from app.progress import set_progress


@celery_app.task(bind=True)
def import_task(self, file_path: str, dest_dir: Optional[str] = None, schema: Optional[Dict[str, Any]] = None, options: Optional[Dict[str, Any]] = None):
    options = options or {}
    schema = schema or {}
    chunk_size = int(options.get("chunk_size", os.getenv("CHUNK_SIZE", 50000)))
    output_format = options.get("output_format", "csv")
    json_array_pointer = options.get("json_array_pointer", "item")

    input_format = detect_format(file_path)

    if dest_dir is None:
        dest_dir = os.getenv("TASK_OUTPUT_DIR", "./output")
    ensure_dir(os.path.join(dest_dir, "_"))

    base_name = os.path.splitext(os.path.basename(file_path))[0]
    clean_output = normalize_output_path(os.path.join(dest_dir, f"{base_name}_clean"), output_format)
    error_output_csv = os.path.join(dest_dir, f"{base_name}_errors.csv")

    total = count_rows(file_path, fmt=input_format)
    processed = 0
    valid_rows = 0
    invalid_rows = 0
    header_written_clean = False
    header_written_errors = False

    unique_state = {}

    set_progress(self, 0, total, message="Starting import")

    # Prepare writers
    clean_writer = get_writer(output_format if output_format in {"csv", "jsonl", "xlsx"} else "csv")
    error_writer = get_writer("csv")

    reader = get_reader(file_path, input_format, chunk_size, json_array_pointer=json_array_pointer)

    sample_errors = []

    for df in reader:
        clean_df, errors_df, unique_state = validate_chunk(df, schema, unique_state)

        if not clean_df.empty:
            clean_writer(clean_output, clean_df, header_written_clean)
            header_written_clean = True
            valid_rows += len(clean_df)

        if not errors_df.empty:
            # ensure error column present
            if "__errors" not in errors_df.columns:
                errors_df["__errors"] = "validation error"
            error_writer(error_output_csv, errors_df, header_written_errors)
            header_written_errors = True
            invalid_rows += len(errors_df)
            if len(sample_errors) < 20:
                sample_errors.extend(errors_df.head(20 - len(sample_errors)).to_dict(orient="records"))

        processed += len(df)
        set_progress(self, min(processed, total), total, message="Importing/validating", extra={"valid_rows": valid_rows, "invalid_rows": invalid_rows})

    result = {
        "status": "completed",
        "file": file_path,
        "total_rows": total,
        "processed": processed,
        "valid_rows": valid_rows,
        "invalid_rows": invalid_rows,
        "clean_output": clean_output,
        "errors_output": error_output_csv,
        "sample_errors": sample_errors,
    }
    set_progress(self, total, total, message="Import completed", extra=result)
    return result

