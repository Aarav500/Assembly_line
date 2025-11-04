import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import io
import os
import json
import uuid
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, abort
from utils.generator import generate_structure, slugify

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev')

# In-memory store of generated prototypes
SESSIONS = {}


def get_seed_or_404(seed):
    data = SESSIONS.get(seed)
    if not data:
        abort(404)
    return data


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


@app.route('/generate', methods=['POST'])
def generate():
    idea = request.form.get('idea', '').strip()
    theme = request.form.get('theme', 'gray')
    fidelity = request.form.get('fidelity', 'low')
    color = request.form.get('color', '#4F46E5')

    if not idea:
        return redirect(url_for('index'))

    seed = uuid.uuid4().hex[:10]
    structure = generate_structure(idea=idea, theme=theme, fidelity=fidelity, primary_color=color, seed=seed)
    SESSIONS[seed] = structure

    # Redirect to first page
    first_page = structure['pages'][0]['slug'] if structure['pages'] else 'home'
    return redirect(url_for('prototype_page', seed=seed, slug=first_page))


@app.route('/prototype/<seed>/', methods=['GET'])
def prototype_root(seed):
    data = get_seed_or_404(seed)
    first_page = data['pages'][0]['slug'] if data['pages'] else 'home'
    return redirect(url_for('prototype_page', seed=seed, slug=first_page))


@app.route('/prototype/<seed>/<slug>', methods=['GET'])
def prototype_page(seed, slug):
    data = get_seed_or_404(seed)
    page = next((p for p in data['pages'] if p['slug'] == slug), None)
    if not page:
        abort(404)
    return render_template(
        'page.html',
        structure=data,
        page=page
    )


@app.route('/api/structure/<seed>', methods=['GET'])
def api_structure(seed):
    data = get_seed_or_404(seed)
    return jsonify(data)


@app.route('/export/<seed>.zip', methods=['GET'])
def export_zip(seed):
    data = get_seed_or_404(seed)

    # Load CSS to inline
    css_path = os.path.join(app.root_path, 'static', 'style.css')
    try:
        with open(css_path, 'r', encoding='utf-8') as f:
            css_text = f.read()
    except Exception:
        css_text = ''

    # Build pages as standalone HTML strings
    html_files = {}
    for p in data['pages']:
        html = render_template(
            'export_page.html',
            structure=data,
            page=p,
            inline_css=css_text
        )
        filename = f"{p['slug']}.html"
        html_files[filename] = html

    # Create index.html pointing to first page
    first_slug = data['pages'][0]['slug'] if data['pages'] else 'home'
    index_html = render_template(
        'export_page.html',
        structure=data,
        page=data['pages'][0] if data['pages'] else {
            'name': 'Home', 'slug': 'home', 'components': []
        },
        inline_css=css_text
    )
    html_files['index.html'] = index_html

    # Package zip in-memory
    import zipfile
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in html_files.items():
            zf.writestr(name, content)
    mem.seek(0)

    fname = f"prototype_{seed}.zip"
    return send_file(mem, mimetype='application/zip', as_attachment=True, download_name=fname)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)



def create_app():
    return app
