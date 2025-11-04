import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
import uuid
import datetime as dt
from typing import Optional, Dict, Any

from flask import Flask, request, jsonify, render_template, send_from_directory, url_for
import pandas as pd

from fairness import compute_fairness_audit
from mitigation import suggest_mitigations, train_baseline_model_with_optional_reweighing
from report import render_html_report

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'uploads')
REPORT_DIR = os.path.join(os.path.dirname(__file__), 'reports')
STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)


def parse_list_param(val: Optional[str]):
    if not val:
        return []
    # allow comma or semicolon separated
    return [v.strip() for v in val.replace(';', ',').split(',') if v.strip()]


def parse_json_param(val: Optional[str]):
    if not val:
        return None
    try:
        return json.loads(val)
    except Exception:
        return None


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/audit', methods=['POST'])
def audit():
    """
    Run an automated bias and fairness audit with optional lightweight mitigation suggestions.
    Accepts multipart/form-data or JSON.
    Fields:
      - file: CSV upload (multipart) or JSON with 'csv' inline content (optional)
      - target_col: str (required)
      - pred_col: str (optional)
      - proba_col: str (optional)
      - protected_attrs: comma-separated list (required)
      - privileged_values: JSON mapping attr -> list of privileged group values (optional)
      - positive_label: value of positive class, default 1
      - threshold: float for hard predictions if proba provided
      - apply_reweighing: bool (optional, default false). If no pred_col, a baseline model is trained; if true, will use reweighing.
    """
    try:
        if request.content_type and 'application/json' in request.content_type:
            payload = request.get_json(force=True)
            csv_content = payload.get('csv')
            if 'file_path' in payload and payload['file_path']:
                df = pd.read_csv(payload['file_path'])
            elif csv_content:
                from io import StringIO
                df = pd.read_csv(StringIO(csv_content))
            else:
                return jsonify({'error': 'CSV data is required (file_path or csv).'}), 400
            target_col = payload.get('target_col')
            pred_col = payload.get('pred_col')
            proba_col = payload.get('proba_col')
            protected_attrs = payload.get('protected_attrs') or []
            if isinstance(protected_attrs, str):
                protected_attrs = parse_list_param(protected_attrs)
            positive_label = payload.get('positive_label', 1)
            privileged_values = payload.get('privileged_values')
            threshold = float(payload.get('threshold', 0.5))
            apply_reweighing = bool(payload.get('apply_reweighing', False))
        else:
            # multipart form
            if 'file' not in request.files:
                return jsonify({'error': 'CSV file is required as multipart field "file".'}), 400
            file = request.files['file']
            if not file.filename:
                return jsonify({'error': 'Empty filename.'}), 400
            fpath = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}_{file.filename}")
            file.save(fpath)
            df = pd.read_csv(fpath)
            target_col = request.form.get('target_col')
            pred_col = request.form.get('pred_col') or None
            proba_col = request.form.get('proba_col') or None
            protected_attrs = parse_list_param(request.form.get('protected_attrs'))
            positive_label = request.form.get('positive_label', 1)
            try:
                positive_label = int(positive_label)
            except Exception:
                pass
            privileged_values = parse_json_param(request.form.get('privileged_values'))
            threshold = float(request.form.get('threshold', 0.5))
            apply_reweighing = request.form.get('apply_reweighing', 'false').lower() in ['1', 'true', 'yes']

        # Basic validations
        if not target_col or target_col not in df.columns:
            return jsonify({'error': 'target_col is required and must exist in the dataset.'}), 400
        if not protected_attrs:
            return jsonify({'error': 'protected_attrs is required and must have at least one attribute name.'}), 400
        for a in protected_attrs:
            if a not in df.columns:
                return jsonify({'error': f'protected attribute {a} not found in dataset.'}), 400

        # If no predictions, optionally train a simple baseline model that excludes protected attributes
        trained_info: Optional[Dict[str, Any]] = None
        if pred_col is None and proba_col is None:
            trained = train_baseline_model_with_optional_reweighing(
                df=df.copy(),
                target_col=target_col,
                protected_attrs=protected_attrs,
                positive_label=positive_label,
                use_reweighing=apply_reweighing,
            )
            df[pred_col := trained['pred_col']] = trained['y_pred']
            df[proba_col := trained['proba_col']] = trained['y_score']
            trained_info = {
                'model_type': trained['model_type'],
                'features_used': trained['features_used'],
                'reweighing_applied': trained['reweighing_applied'],
            }
        elif pred_col is None and proba_col is not None:
            # derive hard predictions using threshold
            if proba_col not in df.columns:
                return jsonify({'error': f'proba_col {proba_col} not found in dataset.'}), 400
            pred_col = f'__pred_from_{proba_col}'
            df[pred_col] = (df[proba_col] >= threshold).astype(int)
        else:
            if pred_col not in df.columns:
                return jsonify({'error': f'pred_col {pred_col} not found in dataset.'}), 400

        # Compute audit
        audit_result = compute_fairness_audit(
            df=df,
            target_col=target_col,
            pred_col=pred_col,
            proba_col=proba_col,
            protected_attrs=protected_attrs,
            privileged_values=privileged_values,
            positive_label=positive_label,
        )

        # Suggestions
        suggestions = suggest_mitigations(audit_result)

        # Bundle report
        audit_id = uuid.uuid4().hex
        timestamp = dt.datetime.utcnow().isoformat() + 'Z'
        payload = {
            'audit_id': audit_id,
            'timestamp_utc': timestamp,
            'config': {
                'target_col': target_col,
                'pred_col': pred_col,
                'proba_col': proba_col,
                'protected_attrs': protected_attrs,
                'privileged_values': privileged_values,
                'positive_label': positive_label,
                'threshold_used': threshold,
                'trained_info': trained_info,
            },
            'metrics': audit_result,
            'suggestions': suggestions,
        }

        # Persist JSON
        json_path = os.path.join(REPORT_DIR, f'{audit_id}.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2)

        # Persist HTML
        html = render_html_report(payload)
        html_path = os.path.join(REPORT_DIR, f'{audit_id}.html')
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html)

        return jsonify({
            'audit_id': audit_id,
            'json_report': url_for('serve_report', filename=f'{audit_id}.json', _external=True),
            'html_report': url_for('serve_report', filename=f'{audit_id}.html', _external=True),
            'summary': audit_result.get('summary', {}),
            'suggestions': suggestions,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/reports/<path:filename>')
def serve_report(filename):
    return send_from_directory(REPORT_DIR, filename, as_attachment=False)


@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(STATIC_DIR, filename, as_attachment=False)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)



def create_app():
    return app


@app.route('/health', methods=['GET'])
def _auto_stub_health():
    return 'Auto-generated stub for /health', 200
