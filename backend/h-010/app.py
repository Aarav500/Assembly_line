import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import io
import json
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, send_file, Response

from alabel.storage import (
    ensure_storage,
    save_pipeline,
    get_pipeline,
    list_pipelines,
    delete_pipeline,
    save_dataset,
    get_dataset_meta,
    list_datasets,
    stream_dataset_records,
    write_jsonl,
    read_jsonl,
    save_run_meta,
    get_run_meta,
    list_runs_for_pipeline,
    list_runs,
    get_run_labels_path,
)
from alabel.pipeline_runner import run_pipeline

app = Flask(__name__)

ensure_storage()

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

# Pipelines
@app.route('/api/pipelines', methods=['POST'])
def create_pipeline():
    try:
        payload = request.get_json(force=True)
        name = payload.get('name')
        label_set = payload.get('label_set')
        lfs = payload.get('lfs', [])
        aggregation = payload.get('aggregation', {"type": "majority_vote", "abstain_label": "ABSTAIN"})
        if not name or not label_set or not isinstance(label_set, list):
            return jsonify({"error": "name and label_set (list) are required"}), 400
        pid = str(uuid.uuid4())
        pipeline = {
            'id': pid,
            'name': name,
            'label_set': label_set,
            'lfs': lfs,
            'aggregation': aggregation,
            'created_at': datetime.utcnow().isoformat() + 'Z'
        }
        save_pipeline(pipeline)
        return jsonify(pipeline), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/pipelines', methods=['GET'])
def get_pipelines():
    return jsonify(list_pipelines())

@app.route('/api/pipelines/<pipeline_id>', methods=['GET'])
def get_pipeline_by_id(pipeline_id):
    pipeline = get_pipeline(pipeline_id)
    if not pipeline:
        return jsonify({"error": "not found"}), 404
    runs = list_runs_for_pipeline(pipeline_id)
    pipeline_with_runs = dict(pipeline)
    pipeline_with_runs['runs'] = runs
    return jsonify(pipeline_with_runs)

@app.route('/api/pipelines/<pipeline_id>', methods=['DELETE'])
def delete_pipeline_by_id(pipeline_id):
    ok = delete_pipeline(pipeline_id)
    if not ok:
        return jsonify({"error": "not found"}), 404
    return jsonify({"deleted": True})

# Datasets
@app.route('/api/datasets', methods=['POST'])
def create_dataset():
    try:
        if request.content_type and request.content_type.startswith('multipart/form-data'):
            # file upload
            if 'file' not in request.files:
                return jsonify({"error": "multipart requires a 'file' field"}), 400
            file = request.files['file']
            name = request.form.get('name') or os.path.basename(file.filename)
            fmt = request.form.get('format', '').lower() or infer_format(file.filename)
            text_field = request.form.get('text_field', 'text')
            dataset_id, meta = save_dataset(name=name, fmt=fmt, text_field=text_field, file_storage=file)
            return jsonify(meta), 201
        else:
            # json body
            payload = request.get_json(force=True, silent=False)
            name = payload.get('name', f"dataset-{uuid.uuid4().hex[:8]}")
            fmt = payload.get('format', 'json')
            text_field = payload.get('text_field', 'text')
            records = payload.get('records')
            if not isinstance(records, list):
                return jsonify({"error": "JSON body must include 'records' array"}), 400
            dataset_id, meta = save_dataset(name=name, fmt='json', text_field=text_field, records=records)
            return jsonify(meta), 201
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/datasets', methods=['GET'])
def get_datasets():
    return jsonify(list_datasets())

@app.route('/api/datasets/<dataset_id>', methods=['GET'])
def get_dataset(dataset_id):
    meta = get_dataset_meta(dataset_id)
    if not meta:
        return jsonify({"error": "not found"}), 404
    # preview first few records
    records = []
    count = 0
    for i, rec in enumerate(stream_dataset_records(dataset_id)):
        if i < 5:
            records.append(rec)
        count += 1
    meta_with_preview = dict(meta)
    meta_with_preview['size'] = count
    meta_with_preview['preview'] = records
    return jsonify(meta_with_preview)

@app.route('/api/datasets/<dataset_id>/export', methods=['GET'])
def export_dataset(dataset_id):
    meta = get_dataset_meta(dataset_id)
    if not meta:
        return jsonify({"error": "not found"}), 404
    export_format = request.args.get('format', 'jsonl')
    # stream original dataset
    if export_format == 'jsonl':
        def generate():
            for rec in stream_dataset_records(dataset_id):
                yield json.dumps(rec, ensure_ascii=False) + "\n"
        return Response(generate(), mimetype='application/x-ndjson', headers={'Content-Disposition': f'attachment; filename="{meta["name"]}.jsonl"'})
    elif export_format == 'csv':
        import csv
        # convert to csv with columns: id, text, ... flattened data keys
        buf = io.StringIO()
        # collect keys
        rows = list(stream_dataset_records(dataset_id))
        if not rows:
            return Response('', mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename="{meta["name"]}.csv"'})
        data_keys = set()
        for r in rows:
            if isinstance(r.get('data'), dict):
                data_keys.update(r['data'].keys())
        fieldnames = ['id', 'text'] + sorted(data_keys)
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            out = {'id': r.get('id'), 'text': r.get('text')}
            if isinstance(r.get('data'), dict):
                for k in data_keys:
                    out[k] = r['data'].get(k)
            writer.writerow(out)
        buf.seek(0)
        return Response(buf.getvalue(), mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename="{meta["name"]}.csv"'})
    else:
        return jsonify({"error": f'unsupported format {export_format}'}), 400

# Run pipeline
@app.route('/api/pipelines/<pipeline_id>/run', methods=['POST'])
def run_pipeline_endpoint(pipeline_id):
    pipeline = get_pipeline(pipeline_id)
    if not pipeline:
        return jsonify({"error": "pipeline not found"}), 404
    payload = request.get_json(force=True)
    dataset_id = payload.get('dataset_id')
    if not dataset_id:
        return jsonify({"error": "dataset_id is required"}), 400
    dataset_meta = get_dataset_meta(dataset_id)
    if not dataset_meta:
        return jsonify({"error": "dataset not found"}), 404
    aggregation = payload.get('aggregation') or pipeline.get('aggregation') or {"type": "majority_vote", "abstain_label": "ABSTAIN"}
    try:
        run_meta = run_pipeline(pipeline, dataset_id, aggregation)
        save_run_meta(run_meta)
        return jsonify(run_meta), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/pipelines/<pipeline_id>/runs', methods=['GET'])
def get_pipeline_runs(pipeline_id):
    if not get_pipeline(pipeline_id):
        return jsonify({"error": "pipeline not found"}), 404
    return jsonify(list_runs_for_pipeline(pipeline_id))

@app.route('/api/runs', methods=['GET'])
def get_all_runs():
    return jsonify(list_runs())

@app.route('/api/runs/<run_id>', methods=['GET'])
def get_run(run_id):
    meta = get_run_meta(run_id)
    if not meta:
        return jsonify({"error": "not found"}), 404
    return jsonify(meta)

@app.route('/api/runs/<run_id>/labels', methods=['GET'])
def get_run_labels(run_id):
    meta = get_run_meta(run_id)
    if not meta:
        return jsonify({"error": "not found"}), 404
    limit = int(request.args.get('limit', '100'))
    path = get_run_labels_path(run_id)
    rows = []
    c = 0
    for row in read_jsonl(path):
        rows.append(row)
        c += 1
        if c >= limit:
            break
    return jsonify({'run_id': run_id, 'count': meta.get('counts', {}).get('total'), 'preview_count': len(rows), 'labels': rows})

@app.route('/api/runs/<run_id>/export', methods=['GET'])
def export_run_labels(run_id):
    meta = get_run_meta(run_id)
    if not meta:
        return jsonify({"error": "not found"}), 404
    export_format = request.args.get('format', 'jsonl')
    path = get_run_labels_path(run_id)
    if export_format == 'jsonl':
        def generate():
            for row in read_jsonl(path):
                yield json.dumps(row, ensure_ascii=False) + "\n"
        return Response(generate(), mimetype='application/x-ndjson', headers={'Content-Disposition': f'attachment; filename="run-{run_id}.jsonl"'})
    elif export_format == 'csv':
        import csv
        rows = list(read_jsonl(path))
        if not rows:
            return Response('', mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename="run-{run_id}.csv"'})
        # Determine columns
        data_keys = set()
        vote_keys = set()
        for r in rows:
            if isinstance(r.get('data'), dict):
                data_keys.update(r['data'].keys())
            if isinstance(r.get('votes'), dict):
                vote_keys.update(r['votes'].keys())
        fieldnames = ['id', 'text', 'label'] + sorted(data_keys) + [f'vote_{k}' for k in sorted(vote_keys)]
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            out = {'id': r.get('id'), 'text': r.get('text'), 'label': r.get('label')}
            if isinstance(r.get('data'), dict):
                for k in data_keys:
                    out[k] = r['data'].get(k)
            if isinstance(r.get('votes'), dict):
                for k in vote_keys:
                    out[f'vote_{k}'] = r['votes'].get(k)
            writer.writerow(out)
        buf.seek(0)
        return Response(buf.getvalue(), mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename="run-{run_id}.csv"'})
    else:
        return jsonify({"error": f'unsupported format {export_format}'}), 400


def infer_format(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith('.jsonl') or lower.endswith('.ndjson'):
        return 'jsonl'
    if lower.endswith('.json'):
        return 'json'
    if lower.endswith('.csv'):
        return 'csv'
    return 'jsonl'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', '5000'))) 



def create_app():
    return app
