import os
import json
import uuid
from typing import Iterable, Dict, List, Optional

DATA_ROOT = os.environ.get('DATA_DIR', 'data')
DATASETS_DIR = os.path.join(DATA_ROOT, 'datasets')
PIPELINES_DIR = os.path.join(DATA_ROOT, 'pipelines')
RUNS_DIR = os.path.join(DATA_ROOT, 'runs')


def ensure_storage():
    os.makedirs(DATA_ROOT, exist_ok=True)
    os.makedirs(DATASETS_DIR, exist_ok=True)
    os.makedirs(PIPELINES_DIR, exist_ok=True)
    os.makedirs(RUNS_DIR, exist_ok=True)


def _write_json(path: str, obj: dict):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _read_json(path: str) -> Optional[dict]:
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def write_jsonl(path: str, rows: Iterable[dict]):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_jsonl(path: str, rows: Iterable[dict]):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'a', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: str) -> Iterable[dict]:
    if not os.path.exists(path):
        return []
    def gen():
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    return gen()

# Pipelines

def save_pipeline(pipeline: dict):
    ensure_storage()
    pid = pipeline['id']
    path = os.path.join(PIPELINES_DIR, f"{pid}.json")
    _write_json(path, pipeline)


def get_pipeline(pipeline_id: str) -> Optional[dict]:
    path = os.path.join(PIPELINES_DIR, f"{pipeline_id}.json")
    return _read_json(path)


def list_pipelines() -> List[dict]:
    ensure_storage()
    out = []
    for fn in os.listdir(PIPELINES_DIR):
        if not fn.endswith('.json'):
            continue
        p = _read_json(os.path.join(PIPELINES_DIR, fn))
        if p:
            out.append(p)
    # sort by created_at desc
    out.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return out


def delete_pipeline(pipeline_id: str) -> bool:
    path = os.path.join(PIPELINES_DIR, f"{pipeline_id}.json")
    if os.path.exists(path):
        os.remove(path)
        return True
    return False

# Datasets

def _normalize_records(records: List[dict], text_field: str) -> Iterable[dict]:
    for i, r in enumerate(records):
        if isinstance(r, dict):
            text = r.get(text_field)
            yield {
                'id': r.get('id', i),
                'text': text,
                'data': r
            }
        else:
            # if just string
            yield {
                'id': i,
                'text': str(r),
                'data': {'value': r}
            }


def _save_dataset_records(dataset_dir: str, normalized: Iterable[dict]):
    data_path = os.path.join(dataset_dir, 'data.jsonl')
    write_jsonl(data_path, normalized)


def save_dataset(name: str, fmt: str, text_field: str, file_storage=None, records: Optional[List[dict]] = None):
    ensure_storage()
    did = str(uuid.uuid4())
    dataset_dir = os.path.join(DATASETS_DIR, did)
    os.makedirs(dataset_dir, exist_ok=True)

    meta = {
        'id': did,
        'name': name,
        'format': fmt,
        'text_field': text_field,
    }

    if file_storage is not None:
        if fmt == 'csv':
            import csv
            # Read CSV rows
            file_storage.stream.seek(0)
            text_stream = file_storage.stream.read().decode('utf-8', errors='ignore')
            reader = csv.DictReader(text_stream.splitlines())
            normalized = _normalize_records(list(reader), text_field)
            _save_dataset_records(dataset_dir, normalized)
        elif fmt == 'jsonl' or fmt == 'ndjson':
            file_storage.stream.seek(0)
            lines = file_storage.stream.read().decode('utf-8', errors='ignore').splitlines()
            recs = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    recs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            normalized = _normalize_records(recs, text_field)
            _save_dataset_records(dataset_dir, normalized)
        elif fmt == 'json':
            file_storage.stream.seek(0)
            try:
                obj = json.loads(file_storage.stream.read().decode('utf-8', errors='ignore'))
            except json.JSONDecodeError as e:
                raise ValueError(f'invalid json: {e}')
            if isinstance(obj, list):
                normalized = _normalize_records(obj, text_field)
                _save_dataset_records(dataset_dir, normalized)
            elif isinstance(obj, dict) and isinstance(obj.get('records'), list):
                normalized = _normalize_records(obj.get('records'), text_field)
                _save_dataset_records(dataset_dir, normalized)
            else:
                raise ValueError('JSON must be array or object with records array')
        else:
            raise ValueError(f'unsupported format: {fmt}')
    else:
        # records provided directly
        if records is None:
            raise ValueError('records array is required when not uploading a file')
        normalized = _normalize_records(records, text_field)
        _save_dataset_records(dataset_dir, normalized)

    meta_path = os.path.join(dataset_dir, 'meta.json')
    _write_json(meta_path, meta)
    return did, meta


def get_dataset_meta(dataset_id: str) -> Optional[dict]:
    meta_path = os.path.join(DATASETS_DIR, dataset_id, 'meta.json')
    return _read_json(meta_path)


def list_datasets() -> List[dict]:
    ensure_storage()
    out = []
    for did in os.listdir(DATASETS_DIR):
        meta = get_dataset_meta(did)
        if meta:
            out.append(meta)
    out.sort(key=lambda x: x.get('name', ''))
    return out


def stream_dataset_records(dataset_id: str) -> Iterable[dict]:
    path = os.path.join(DATASETS_DIR, dataset_id, 'data.jsonl')
    return read_jsonl(path)

# Runs

def ensure_run_dir(run_id: str) -> str:
    path = os.path.join(RUNS_DIR, run_id)
    os.makedirs(path, exist_ok=True)
    return path


def save_run_meta(run_meta: dict):
    path = os.path.join(RUNS_DIR, run_meta['id'], 'meta.json')
    _write_json(path, run_meta)


def get_run_meta(run_id: str) -> Optional[dict]:
    path = os.path.join(RUNS_DIR, run_id, 'meta.json')
    return _read_json(path)


def get_run_labels_path(run_id: str) -> str:
    return os.path.join(RUNS_DIR, run_id, 'labels.jsonl')


def list_runs_for_pipeline(pipeline_id: str) -> List[dict]:
    ensure_storage()
    out = []
    for rid in os.listdir(RUNS_DIR):
        meta = get_run_meta(rid)
        if meta and meta.get('pipeline_id') == pipeline_id:
            out.append(meta)
    out.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return out


def list_runs() -> List[dict]:
    ensure_storage()
    out = []
    for rid in os.listdir(RUNS_DIR):
        meta = get_run_meta(rid)
        if meta:
            out.append(meta)
    out.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return out

