import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
app.config['SECRET_KEY'] = 'change-this-secret-key'

CATEGORY_MAP = {
    'must': 4,
    'm': 4,
    'should': 3,
    's': 3,
    'could': 2,
    'c': 2,
    'wont': 1,
    "won't": 1,
    'w': 1,
}

CATEGORY_DISPLAY = {
    4: 'Must',
    3: 'Should',
    2: 'Could',
    1: "Won't"
}


def to_float(val, default=0.0):
    try:
        if val is None:
            return default
        s = str(val).strip()
        if s == '':
            return default
        return float(s)
    except Exception:
        return default


def normalize_confidence(val):
    c = to_float(val, 0.0)
    # allow 0-1 or 0-100
    if c > 1:
        c = c / 100.0
    # clamp 0..1
    if c < 0:
        c = 0.0
    if c > 1:
        c = 1.0
    return c


def compute_rice(items):
    result = []
    for it in items:
        name = (it.get('name') or '').strip()
        if not name:
            continue
        reach = to_float(it.get('reach'))
        impact = to_float(it.get('impact'))
        confidence = normalize_confidence(it.get('confidence'))
        effort = to_float(it.get('effort'))
        notes = (it.get('notes') or '').strip()
        score = 0.0
        warning = None
        if effort <= 0:
            warning = 'Effort must be > 0 for RICE. Score set to 0.'
            score = 0.0
        else:
            score = (reach * impact * confidence) / effort
        result.append({
            'name': name,
            'reach': reach,
            'impact': impact,
            'confidence': confidence,  # 0..1
            'confidence_pct': round(confidence * 100.0, 2),
            'effort': effort,
            'score': score,
            'notes': notes,
            'warning': warning
        })
    # sort by score desc, then effort asc, then name
    result.sort(key=lambda x: (-x['score'], x['effort'], x['name'].lower()))
    # add rank
    for idx, r in enumerate(result, start=1):
        r['rank'] = idx
    return result


def parse_category(cat_raw):
    if cat_raw is None:
        return 1
    k = str(cat_raw).strip().lower()
    return CATEGORY_MAP.get(k, 1)


def compute_moscow(items):
    result = []
    for it in items:
        name = (it.get('name') or '').strip()
        if not name:
            continue
        cat_priority = parse_category(it.get('category'))
        effort = to_float(it.get('effort'))
        value = to_float(it.get('business_value'))
        notes = (it.get('notes') or '').strip()
        ratio = 0.0
        warning = None
        if effort <= 0:
            # if effort unknown, prefer sorting by value only
            warning = 'Effort must be > 0 for ratio. Using value as tiebreaker.'
            ratio = 0.0
        else:
            ratio = value / effort
        result.append({
            'name': name,
            'category_priority': cat_priority,
            'category_display': CATEGORY_DISPLAY.get(cat_priority, "Won't"),
            'business_value': value,
            'effort': effort,
            'ratio': ratio,
            'notes': notes,
            'warning': warning
        })
    # sort by category desc, then ratio desc, then value desc, then effort asc
    result.sort(key=lambda x: (-x['category_priority'], -x['ratio'], -x['business_value'], x['effort']))
    for idx, r in enumerate(result, start=1):
        r['rank'] = idx
    return result


def collect_items_from_form(form, method):
    # We rely on a row_count hidden field and index-based arrays
    try:
        row_count = int(form.get('row_count', '0'))
    except ValueError:
        row_count = 0

    items = []
    # Use getlist to access arrays
    names = form.getlist('name[]')

    if method == 'rice':
        reaches = form.getlist('reach[]')
        impacts = form.getlist('impact[]')
        confidences = form.getlist('confidence[]')
        efforts = form.getlist('effort[]')
        notes = form.getlist('notes[]')
        max_len = max(len(names), len(reaches), len(impacts), len(confidences), len(efforts), len(notes))
        for i in range(max(row_count, max_len)):
            items.append({
                'name': names[i] if i < len(names) else '',
                'reach': reaches[i] if i < len(reaches) else '',
                'impact': impacts[i] if i < len(impacts) else '',
                'confidence': confidences[i] if i < len(confidences) else '',
                'effort': efforts[i] if i < len(efforts) else '',
                'notes': notes[i] if i < len(notes) else ''
            })
    else:
        cats = form.getlist('category[]')
        values = form.getlist('business_value[]')
        efforts = form.getlist('effort[]')
        notes = form.getlist('notes[]')
        max_len = max(len(names), len(cats), len(values), len(efforts), len(notes))
        for i in range(max(row_count, max_len)):
            items.append({
                'name': names[i] if i < len(names) else '',
                'category': cats[i] if i < len(cats) else '',
                'business_value': values[i] if i < len(values) else '',
                'effort': efforts[i] if i < len(efforts) else '',
                'notes': notes[i] if i < len(notes) else ''
            })
    return items


@app.route('/', methods=['GET'])
def index():
    # Optionally provide sample data via query param
    method = request.args.get('method', 'rice').lower()
    sample = request.args.get('sample', '0') == '1'
    prefill = []
    if sample and method == 'rice':
        prefill = [
            {'name': 'User Onboarding', 'reach': '500', 'impact': '3', 'confidence': '80', 'effort': '8', 'notes': 'Improve activation'},
            {'name': 'Dark Mode', 'reach': '200', 'impact': '2', 'confidence': '0.9', 'effort': '5', 'notes': ''},
            {'name': 'Billing Revamp', 'reach': '150', 'impact': '4', 'confidence': '70', 'effort': '13', 'notes': 'High complexity'}
        ]
    elif sample and method == 'moscow':
        prefill = [
            {'name': 'SSO Integration', 'category': 'Must', 'business_value': '90', 'effort': '8', 'notes': ''},
            {'name': 'Custom Reports', 'category': 'Should', 'business_value': '70', 'effort': '10', 'notes': ''},
            {'name': 'Theme Editor', 'category': 'Could', 'business_value': '40', 'effort': '5', 'notes': ''}
        ]
    return render_template('index.html', method=method, results=None, items=prefill)


@app.route('/prioritize', methods=['POST'])
def prioritize():
    method = request.form.get('method', 'rice').lower()
    items = collect_items_from_form(request.form, method)

    if method == 'rice':
        results = compute_rice(items)
    else:
        method = 'moscow'
        results = compute_moscow(items)

    return render_template('index.html', method=method, results=results, items=items)


@app.route('/api/prioritize', methods=['POST'])
def api_prioritize():
    data = request.get_json(silent=True) or {}
    method = str(data.get('method', 'rice')).lower()
    items = data.get('items', [])

    if method == 'rice':
        results = compute_rice(items)
    else:
        method = 'moscow'
        results = compute_moscow(items)
    return jsonify({'method': method, 'results': results})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)



def create_app():
    return app


@app.route('/features', methods=['POST'])
def _auto_stub_features():
    return 'Auto-generated stub for /features', 200
