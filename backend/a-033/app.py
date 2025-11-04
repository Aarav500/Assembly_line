import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, render_template, request, jsonify, redirect, url_for
from feature_flags import FeatureFlagStore, detect_flags, is_enabled, jinja_flag
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
STORE_PATH = os.path.join(DATA_DIR, 'feature_flags.json')

app = Flask(__name__)
app.config['FEATURE_FLAGS_STORE'] = STORE_PATH
app.config['FEATURE_SCAN_DIR'] = os.getenv('FEATURE_SCAN_DIR', BASE_DIR)

store = FeatureFlagStore(STORE_PATH)

# Make flag() available in Jinja templates
app.jinja_env.globals['flag'] = jinja_flag

@app.route('/')
def index():
    return redirect(url_for('flags_ui'))

@app.route('/flags')
def flags_ui():
    flags = store.get_flags()
    flags_list = []
    for name, meta in sorted(flags.items()):
        flags_list.append({
            'name': name,
            'enabled': bool(meta.get('enabled', False)),
            'stale': bool(meta.get('stale', False)),
            'description': meta.get('description') or '',
            'locations': meta.get('locations', []),
            'created_at': meta.get('created_at'),
            'last_seen': meta.get('last_seen'),
        })
    last_scan = store.get_last_scan()
    return render_template('flags.html', flags=flags_list, last_scan=last_scan)

@app.route('/api/flags', methods=['GET'])
def api_list_flags():
    flags = store.get_flags()
    out = []
    for name, meta in sorted(flags.items()):
        out.append({
            'name': name,
            'enabled': bool(meta.get('enabled', False)),
            'stale': bool(meta.get('stale', False)),
            'description': meta.get('description') or '',
            'locations': meta.get('locations', []),
            'created_at': meta.get('created_at'),
            'last_seen': meta.get('last_seen'),
        })
    return jsonify({
        'flags': out,
        'last_scan': store.get_last_scan(),
    })

@app.route('/api/flags/<name>', methods=['POST'])
def api_toggle_flag(name):
    data = request.get_json(silent=True) or {}
    if 'enabled' not in data:
        return jsonify({'error': 'Missing "enabled" boolean'}), 400
    enabled = bool(data['enabled'])
    try:
        store.set_flag_enabled(name, enabled)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    return jsonify({'name': name, 'enabled': enabled})

@app.route('/api/rescan', methods=['POST'])
def api_rescan():
    scan_dir = app.config['FEATURE_SCAN_DIR']
    detected = detect_flags(scan_dir)
    summary = store.merge_detected(detected)
    store.set_last_scan(datetime.utcnow().isoformat())
    return jsonify({'ok': True, 'summary': summary, 'last_scan': store.get_last_scan()})

# Example route demonstrating feature flag usage in views/templates
@app.route('/demo')
def demo():
    message = 'Welcome!'
    if is_enabled('beta_banner'):
        message += ' You are seeing the beta banner.'
    return render_template('demo.html', message=message)

if __name__ == '__main__':
    os.makedirs(DATA_DIR, exist_ok=True)
    # Initial scan on first run if store is empty
    if not os.path.exists(STORE_PATH):
        detected = detect_flags(app.config['FEATURE_SCAN_DIR'])
        store.merge_detected(detected)
        store.set_last_scan(datetime.utcnow().isoformat())
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '5000')), debug=True)



def create_app():
    return app
