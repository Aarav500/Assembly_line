import uuid
from datetime import datetime
from typing import Dict

from .storage import stream_dataset_records, ensure_run_dir, write_jsonl
from .labeling import build_lfs, build_aggregator


def run_pipeline(pipeline: Dict, dataset_id: str, aggregation_cfg: Dict) -> Dict:
    lfs = build_lfs(pipeline.get('lfs', []))
    if not lfs:
        raise ValueError('Pipeline has no labeling functions')
    aggregator = build_aggregator(aggregation_cfg, pipeline.get('label_set', []))

    run_id = str(uuid.uuid4())
    output_path = ensure_run_dir(run_id)
    labels_path = f"{output_path}/labels.jsonl"

    counts = {
        'total': 0,
        'labeled': 0,
        'abstain': 0,
        'per_label': {}
    }

    def row_iter():
        for row in stream_dataset_records(dataset_id):
            counts['total'] += 1
            vote_map = {}
            votes = []
            for lf in lfs:
                v = lf.apply(row)
                vote_map[lf.name] = v
                votes.append(v)
            final = aggregator.aggregate(votes)
            if final is None or final == aggregation_cfg.get('abstain_label', None):
                counts['abstain'] += 1
            else:
                counts['labeled'] += 1
                counts['per_label'][final] = counts['per_label'].get(final, 0) + 1
            yield {
                'id': row.get('id'),
                'text': row.get('text'),
                'data': row.get('data'),
                'label': final,
                'votes': vote_map
            }

    write_jsonl(labels_path, row_iter())

    run_meta = {
        'id': run_id,
        'pipeline_id': pipeline['id'],
        'dataset_id': dataset_id,
        'created_at': datetime.utcnow().isoformat() + 'Z',
        'counts': counts,
        'output_path': output_path,
        'labels_path': labels_path,
        'aggregation': aggregation_cfg,
        'pipeline_name': pipeline.get('name'),
    }
    return run_meta

