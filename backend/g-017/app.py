import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from flask import Flask, request, jsonify, send_from_directory
from privacy.anonymizer import Anonymizer
from privacy.k_anonymity import KAnalyzer

app = Flask(__name__, static_folder='static', static_url_path='')


def parse_json_request(req):
    try:
        payload = req.get_json(force=True)
        if not isinstance(payload, dict):
            return None, ("Invalid JSON body", 400)
        return payload, None
    except Exception as e:
        return None, (f"Invalid JSON: {e}", 400)


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/api/check-k', methods=['POST'])
def check_k():
    body, err = parse_json_request(request)
    if err:
        return jsonify({"error": err[0]}), err[1]

    data = body.get('data')
    quasi_identifiers = body.get('quasi_identifiers')
    k = body.get('k')
    types = body.get('types')  # optional, map field->type

    if not isinstance(data, list) or not all(isinstance(r, dict) for r in data):
        return jsonify({"error": "data must be a list of objects"}), 400
    if not isinstance(quasi_identifiers, list) or not quasi_identifiers:
        return jsonify({"error": "quasi_identifiers must be a non-empty list"}), 400

    analyzer = KAnalyzer(types=types)
    try:
        metrics = analyzer.analyze(data, quasi_identifiers)
    except Exception as e:
        return jsonify({"error": f"Failed to analyze k-anonymity: {e}"}), 400

    resp = {
        "min_class_size": metrics['min_class_size'],
        "current_k": metrics['min_class_size'],
        "equivalence_class_count": metrics['equivalence_class_count'],
        "violating_class_count": metrics['violating_class_count'],
        "record_count": metrics['record_count'],
    }
    if k is not None:
        try:
            k_int = int(k)
        except Exception:
            return jsonify({"error": "k must be an integer"}), 400
        resp["requested_k"] = k_int
        resp["achieves_k"] = metrics['min_class_size'] >= k_int

    # Optionally return sample of classes
    sample = metrics.get('classes_sample', [])
    resp['classes_sample'] = sample

    return jsonify(resp)


@app.route('/api/anonymize', methods=['POST'])
def anonymize():
    body, err = parse_json_request(request)
    if err:
        return jsonify({"error": err[0]}), err[1]

    data = body.get('data')
    quasi_identifiers = body.get('quasi_identifiers')
    k = body.get('k', 5)
    suppress = body.get('suppress', True)
    max_suppression_rate = body.get('max_suppression_rate', 0.2)
    auto = body.get('auto', True)
    strategies = body.get('strategies')  # optional per-field strategies
    types = body.get('types')  # optional per-field types
    mask_fields = body.get('mask_fields', {})  # optional per-field masking options

    if not isinstance(data, list) or not all(isinstance(r, dict) for r in data):
        return jsonify({"error": "data must be a list of objects"}), 400
    if not isinstance(quasi_identifiers, list) or not quasi_identifiers:
        return jsonify({"error": "quasi_identifiers must be a non-empty list"}), 400
    try:
        k = int(k)
        if k < 2:
            return jsonify({"error": "k must be >= 2"}), 400
    except Exception:
        return jsonify({"error": "k must be an integer"}), 400

    anonymizer = Anonymizer(types=types)
    try:
        result = anonymizer.anonymize(
            data=data,
            quasi_identifiers=quasi_identifiers,
            k=k,
            auto=auto,
            strategies=strategies,
            suppress=suppress,
            max_suppression_rate=max_suppression_rate,
            mask_fields=mask_fields,
        )
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to anonymize: {e}"}), 500

    return jsonify(result)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)



def create_app():
    return app


@app.route('/check-k-anonymity', methods=['POST'])
def _auto_stub_check_k_anonymity():
    return 'Auto-generated stub for /check-k-anonymity', 200


@app.route('/hash-identifier', methods=['POST'])
def _auto_stub_hash_identifier():
    return 'Auto-generated stub for /hash-identifier', 200
