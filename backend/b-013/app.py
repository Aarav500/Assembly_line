import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import io
import json
import os
from uuid import uuid4
from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify
from generator.research_generator import generate_paper
from generator.latex_exporter import paper_to_latex

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

# In-memory store for generated papers
PAPER_STORE = {}


def normalize_length(length):
    if isinstance(length, str):
        length = length.lower().strip()
        if length in ['short', 's']:
            return 'short'
        if length in ['long', 'l']:
            return 'long'
        return 'medium'
    return 'medium'


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


@app.route('/generate', methods=['POST'])
def generate():
    topic = request.form.get('topic', '').strip()
    title = request.form.get('title', '').strip()
    authors = request.form.get('authors', '').strip() or 'Automated Researcher'
    keywords = request.form.get('keywords', '').strip()
    seed_refs = request.form.get('references', '').strip()
    length = normalize_length(request.form.get('length', 'medium'))
    style = request.form.get('citation_style', 'numeric')

    if not topic and not title:
        topic = 'General Research Topic'

    paper = generate_paper(
        topic=topic or title,
        title=title or None,
        authors=authors,
        length=length,
        keywords=keywords,
        references_text=seed_refs,
        citation_style=style,
    )

    paper_id = str(uuid4())
    PAPER_STORE[paper_id] = paper
    return redirect(url_for('paper_view', paper_id=paper_id))


@app.route('/paper/<paper_id>', methods=['GET'])
def paper_view(paper_id):
    paper = PAPER_STORE.get(paper_id)
    if not paper:
        return render_template('result.html', error='Paper not found.'), 404
    return render_template('result.html', paper=paper, paper_id=paper_id)


@app.route('/download_latex/<paper_id>', methods=['GET'])
def download_latex(paper_id):
    paper = PAPER_STORE.get(paper_id)
    if not paper:
        return 'Paper not found', 404
    latex_str = paper_to_latex(paper)
    filename_safe = paper.get('title', 'paper').replace(' ', '_')[:64]
    buf = io.BytesIO(latex_str.encode('utf-8'))
    return send_file(
        buf,
        as_attachment=True,
        download_name=f"{filename_safe}.tex",
        mimetype='application/x-tex'
    )


@app.route('/api/generate', methods=['POST'])
def api_generate():
    try:
        payload = request.get_json(force=True)
    except Exception:
        return jsonify({'error': 'Invalid JSON'}), 400

    topic = payload.get('topic') or payload.get('title') or 'General Research Topic'
    title = payload.get('title')
    authors = payload.get('authors') or 'Automated Researcher'
    keywords = payload.get('keywords') or ''
    references_text = payload.get('references_text') or payload.get('references') or ''
    length = normalize_length(payload.get('length') or 'medium')
    style = payload.get('citation_style') or 'numeric'

    paper = generate_paper(
        topic=topic,
        title=title,
        authors=authors,
        length=length,
        keywords=keywords,
        references_text=references_text,
        citation_style=style,
    )

    paper_id = str(uuid4())
    PAPER_STORE[paper_id] = paper

    return jsonify({'paper_id': paper_id, 'paper': paper})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)



def create_app():
    return app
