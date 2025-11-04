import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify, abort

from utils.generator import generate_docs, default_project_template, slugify

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data', 'projects')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output', 'projects')
DOC_FILENAMES = {
    'onboarding': 'onboarding_checklist.md',
    'dev_guide': 'dev_environment_guide.md'
}

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True


def list_projects():
    items = []
    for fname in sorted(os.listdir(DATA_DIR)):
        if not fname.endswith('.json'):
            continue
        fpath = os.path.join(DATA_DIR, fname)
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                proj = json.load(f)
            slug = fname[:-5]
            items.append({
                'slug': slug,
                'name': proj.get('name', slug),
                'description': proj.get('description', ''),
                'updated_at': proj.get('updated_at', None)
            })
        except Exception:
            continue
    return items


def load_project(slug):
    path = os.path.join(DATA_DIR, f'{slug}.json')
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        proj = json.load(f)
    return proj


def save_project(project, slug=None):
    if not slug:
        slug = slugify(project.get('slug') or project.get('name', 'project'))
    project['slug'] = slug
    project['updated_at'] = datetime.utcnow().isoformat()
    path = os.path.join(DATA_DIR, f'{slug}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(project, f, indent=2)
    return slug


def project_output_dir(slug):
    out_dir = os.path.join(OUTPUT_DIR, slug)
    os.makedirs(out_dir, exist_ok=True)
    return out_dir


def ensure_docs(slug, project=None):
    out_dir = project_output_dir(slug)
    onboarding_path = os.path.join(out_dir, DOC_FILENAMES['onboarding'])
    dev_guide_path = os.path.join(out_dir, DOC_FILENAMES['dev_guide'])
    if os.path.exists(onboarding_path) and os.path.exists(dev_guide_path):
        return onboarding_path, dev_guide_path
    if project is None:
        project = load_project(slug)
    if not project:
        return None, None
    rendered = generate_docs(project)
    with open(onboarding_path, 'w', encoding='utf-8') as f:
        f.write(rendered['onboarding'])
    with open(dev_guide_path, 'w', encoding='utf-8') as f:
        f.write(rendered['dev_guide'])
    return onboarding_path, dev_guide_path


@app.route('/')
def index():
    projects = list_projects()
    return render_template('index.html', projects=projects)


@app.route('/projects/new', methods=['GET'])
def new_project():
    template_json = json.dumps(default_project_template(), indent=2)
    return render_template('new_project.html', template_json=template_json)


@app.route('/projects', methods=['POST'])
def create_project():
    project_json = request.form.get('project_json', '').strip()
    if not project_json:
        abort(400, description='Missing project_json')
    try:
        project = json.loads(project_json)
    except json.JSONDecodeError as e:
        abort(400, description=f'Invalid JSON: {e}')
    slug = slugify(project.get('slug') or project.get('name') or 'project')
    slug = save_project(project, slug)
    ensure_docs(slug, project)
    return redirect(url_for('view_project', slug=slug))


@app.route('/projects/<slug>')
def view_project(slug):
    project = load_project(slug)
    if not project:
        abort(404)
    onboarding_path, dev_guide_path = ensure_docs(slug, project)
    onboarding_content = ''
    dev_guide_content = ''
    if onboarding_path and os.path.exists(onboarding_path):
        with open(onboarding_path, 'r', encoding='utf-8') as f:
            onboarding_content = f.read()
    if dev_guide_path and os.path.exists(dev_guide_path):
        with open(dev_guide_path, 'r', encoding='utf-8') as f:
            dev_guide_content = f.read()
    return render_template('project.html', project=project, onboarding_content=onboarding_content, dev_guide_content=dev_guide_content, doc_filenames=DOC_FILENAMES)


@app.route('/projects/<slug>/docs/<doc_name>')
def download_doc(slug, doc_name):
    if doc_name not in DOC_FILENAMES.values():
        abort(404)
    out_dir = project_output_dir(slug)
    path = os.path.join(out_dir, doc_name)
    if not os.path.exists(path):
        abort(404)
    return send_from_directory(out_dir, doc_name, as_attachment=True)


@app.route('/api/projects', methods=['GET'])
def api_list_projects():
    return jsonify({
        'projects': list_projects()
    })


@app.route('/api/projects/<slug>', methods=['GET'])
def api_get_project(slug):
    project = load_project(slug)
    if not project:
        abort(404)
    return jsonify(project)


@app.route('/api/projects/<slug>/docs', methods=['GET'])
def api_get_docs(slug):
    project = load_project(slug)
    if not project:
        abort(404)
    onboarding_path, dev_guide_path = ensure_docs(slug, project)
    result = {}
    if onboarding_path and os.path.exists(onboarding_path):
        with open(onboarding_path, 'r', encoding='utf-8') as f:
            result['onboarding'] = f.read()
    if dev_guide_path and os.path.exists(dev_guide_path):
        with open(dev_guide_path, 'r', encoding='utf-8') as f:
            result['dev_guide'] = f.read()
    return jsonify(result)


@app.route('/api/generate', methods=['POST'])
def api_generate():
    try:
        payload = request.get_json(force=True)
    except Exception:
        abort(400, description='Invalid JSON body')
    project = payload.get('project') or payload
    persist = payload.get('persist', False)
    slug = slugify(project.get('slug') or project.get('name') or 'project')
    rendered = generate_docs(project)
    response = {
        'slug': slug,
        'onboarding': rendered['onboarding'],
        'dev_guide': rendered['dev_guide']
    }
    if persist:
        slug = save_project(project, slug)
        out_dir = project_output_dir(slug)
        with open(os.path.join(out_dir, DOC_FILENAMES['onboarding']), 'w', encoding='utf-8') as f:
            f.write(rendered['onboarding'])
        with open(os.path.join(out_dir, DOC_FILENAMES['dev_guide']), 'w', encoding='utf-8') as f:
            f.write(rendered['dev_guide'])
        response['saved'] = True
        response['paths'] = {
            'project_json': os.path.join('data', 'projects', f'{slug}.json'),
            'onboarding': os.path.join('output', 'projects', slug, DOC_FILENAMES['onboarding']),
            'dev_guide': os.path.join('output', 'projects', slug, DOC_FILENAMES['dev_guide'])
        }
    return jsonify(response)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)



def create_app():
    return app
