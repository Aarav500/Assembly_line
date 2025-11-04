import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import time
from datetime import datetime
from flask import Flask, jsonify, render_template, request, redirect, url_for, abort
from dotenv import load_dotenv

from models import db, Prompt, PromptVersion, RunHistory
from services.llm import run_llm
from services.metrics import compute_prompt_metrics

load_dotenv()


def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///app.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JSON_SORT_KEYS'] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()

    @app.route('/')
    def index():
        prompts = Prompt.query.order_by(Prompt.updated_at.desc()).all()
        prompt_cards = []
        for p in prompts:
            metrics = compute_prompt_metrics(p.id)
            prompt_cards.append({
                'id': p.id,
                'name': p.name,
                'description': p.description,
                'versions': len(p.versions),
                'total_runs': metrics['summary']['total_runs'],
                'avg_latency_ms': metrics['summary']['avg_latency_ms'],
                'pass_rate': metrics['summary']['pass_rate'],
                'avg_score': metrics['summary']['avg_score'],
            })
        return render_template('index.html', prompts=prompt_cards)

    @app.route('/prompts/<int:prompt_id>')
    def prompt_detail(prompt_id):
        prompt = Prompt.query.get_or_404(prompt_id)
        versions = PromptVersion.query.filter_by(prompt_id=prompt.id).order_by(PromptVersion.version_number.desc()).all()
        default_version_id = prompt.default_version_id
        metrics = compute_prompt_metrics(prompt.id)
        latest_runs = RunHistory.query.filter_by(prompt_id=prompt.id).order_by(RunHistory.created_at.desc()).limit(25).all()
        return render_template('prompt_detail.html', prompt=prompt, versions=versions, default_version_id=default_version_id, metrics=metrics, latest_runs=latest_runs)

    # API endpoints

    @app.route('/api/prompts', methods=['GET'])
    def api_list_prompts():
        prompts = Prompt.query.order_by(Prompt.updated_at.desc()).all()
        data = []
        for p in prompts:
            metrics = compute_prompt_metrics(p.id)
            data.append({
                'id': p.id,
                'name': p.name,
                'description': p.description,
                'default_version_id': p.default_version_id,
                'versions': [{'id': v.id, 'version_number': v.version_number} for v in p.versions],
                'metrics': metrics['summary']
            })
        return jsonify(data)

    @app.route('/api/prompts', methods=['POST'])
    def api_create_prompt():
        payload = request.get_json(force=True)
        name = (payload.get('name') or '').strip()
        description = (payload.get('description') or '').strip()
        initial_content = (payload.get('initial_content') or '').strip()
        if not name:
            return jsonify({'error': 'Name is required'}), 400
        if Prompt.query.filter_by(name=name).first():
            return jsonify({'error': 'Prompt name already exists'}), 409
        now = datetime.utcnow()
        prompt = Prompt(name=name, description=description, created_at=now, updated_at=now)
        db.session.add(prompt)
        db.session.flush()
        vnum = 1
        version = PromptVersion(prompt_id=prompt.id, version_number=vnum, content=initial_content or 'Enter your prompt content here...', created_at=now)
        db.session.add(version)
        db.session.flush()
        prompt.default_version_id = version.id
        db.session.commit()
        return jsonify({'id': prompt.id, 'name': prompt.name, 'description': prompt.description, 'default_version_id': prompt.default_version_id, 'version': {'id': version.id, 'version_number': version.version_number, 'content': version.content}}), 201

    @app.route('/api/prompts/<int:prompt_id>', methods=['GET'])
    def api_get_prompt(prompt_id):
        prompt = Prompt.query.get_or_404(prompt_id)
        versions = PromptVersion.query.filter_by(prompt_id=prompt.id).order_by(PromptVersion.version_number.asc()).all()
        metrics = compute_prompt_metrics(prompt.id)
        return jsonify({
            'id': prompt.id,
            'name': prompt.name,
            'description': prompt.description,
            'default_version_id': prompt.default_version_id,
            'versions': [
                {'id': v.id, 'version_number': v.version_number, 'content': v.content, 'created_at': v.created_at.isoformat()} for v in versions
            ],
            'metrics': metrics
        })

    @app.route('/api/prompts/<int:prompt_id>/versions', methods=['POST'])
    def api_create_version(prompt_id):
        prompt = Prompt.query.get_or_404(prompt_id)
        payload = request.get_json(force=True)
        content = (payload.get('content') or '').strip()
        if not content:
            return jsonify({'error': 'Content is required'}), 400
        now = datetime.utcnow()
        last_ver = db.session.query(db.func.max(PromptVersion.version_number)).filter_by(prompt_id=prompt.id).scalar() or 0
        version = PromptVersion(prompt_id=prompt.id, version_number=last_ver + 1, content=content, created_at=now)
        db.session.add(version)
        db.session.flush()
        # Optionally set as default
        if payload.get('set_default', True):
            prompt.default_version_id = version.id
        prompt.updated_at = now
        db.session.commit()
        return jsonify({'id': version.id, 'version_number': version.version_number, 'content': version.content, 'created_at': version.created_at.isoformat(), 'default_version_id': prompt.default_version_id}), 201

    @app.route('/api/prompts/<int:prompt_id>/default_version', methods=['POST'])
    def api_set_default_version(prompt_id):
        prompt = Prompt.query.get_or_404(prompt_id)
        payload = request.get_json(force=True)
        version_id = payload.get('version_id')
        version = PromptVersion.query.filter_by(id=version_id, prompt_id=prompt.id).first()
        if not version:
            return jsonify({'error': 'Version not found for this prompt'}), 404
        prompt.default_version_id = version.id
        prompt.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'ok': True, 'default_version_id': prompt.default_version_id})

    @app.route('/api/run', methods=['POST'])
    def api_run_prompt():
        payload = request.get_json(force=True)
        prompt_id = payload.get('prompt_id')
        version_id = payload.get('version_id')
        input_text = payload.get('input_text') or ''
        parameters = payload.get('parameters') or {}
        provider = payload.get('provider') or os.getenv('LLM_PROVIDER', 'mock')
        model = payload.get('model') or os.getenv('LLM_MODEL', '')

        prompt = Prompt.query.get_or_404(prompt_id)
        version = None
        if version_id:
            version = PromptVersion.query.filter_by(id=version_id, prompt_id=prompt.id).first()
            if not version:
                return jsonify({'error': 'Version not found for this prompt'}), 404
        else:
            if prompt.default_version_id:
                version = PromptVersion.query.get(prompt.default_version_id)
            else:
                version = PromptVersion.query.filter_by(prompt_id=prompt.id).order_by(PromptVersion.version_number.desc()).first()
        if not version:
            return jsonify({'error': 'No versions available for this prompt'}), 400

        # Render template: replace {{input}} with provided input_text
        final_prompt = version.content.replace('{{input}}', input_text)

        t0 = time.time()
        result = run_llm(final_prompt, provider=provider, model=model)
        latency_ms = int((time.time() - t0) * 1000)

        output_text = result.get('output_text') or ''
        error = result.get('error')
        model_used = result.get('model')

        def approx_tokens(text):
            # rough heuristic: 1 token ~ 4 chars in English
            return max(1, int(len(text) / 4))

        tokens_prompt = approx_tokens(final_prompt)
        tokens_output = approx_tokens(output_text)

        run = RunHistory(
            prompt_id=prompt.id,
            prompt_version_id=version.id,
            input_text=input_text,
            output_text=output_text,
            latency_ms=latency_ms,
            tokens_prompt=tokens_prompt,
            tokens_output=tokens_output,
            created_at=datetime.utcnow(),
            success=None,
            score=None,
            notes=None,
            parameters=parameters,
            model_name=model_used,
            provider=provider,
            error=error
        )
        db.session.add(run)
        db.session.commit()

        return jsonify({
            'id': run.id,
            'prompt_id': run.prompt_id,
            'prompt_version_id': run.prompt_version_id,
            'input_text': run.input_text,
            'output_text': run.output_text,
            'latency_ms': run.latency_ms,
            'tokens_prompt': run.tokens_prompt,
            'tokens_output': run.tokens_output,
            'created_at': run.created_at.isoformat(),
            'success': run.success,
            'score': run.score,
            'model': model_used,
            'provider': provider,
            'error': error
        })

    @app.route('/api/history', methods=['GET'])
    def api_history():
        prompt_id = request.args.get('prompt_id', type=int)
        version_id = request.args.get('version_id', type=int)
        q = RunHistory.query
        if prompt_id:
            q = q.filter_by(prompt_id=prompt_id)
        if version_id:
            q = q.filter_by(prompt_version_id=version_id)
        q = q.order_by(RunHistory.created_at.desc())
        runs = q.limit(200).all()
        data = []
        for r in runs:
            data.append({
                'id': r.id,
                'prompt_id': r.prompt_id,
                'prompt_version_id': r.prompt_version_id,
                'input_text': r.input_text,
                'output_text': r.output_text,
                'latency_ms': r.latency_ms,
                'tokens_prompt': r.tokens_prompt,
                'tokens_output': r.tokens_output,
                'created_at': r.created_at.isoformat(),
                'success': r.success,
                'score': r.score,
                'notes': r.notes,
                'model': r.model_name,
                'provider': r.provider,
                'error': r.error
            })
        return jsonify(data)

    @app.route('/api/history/<int:run_id>/evaluate', methods=['POST'])
    def api_evaluate_run(run_id):
        run = RunHistory.query.get_or_404(run_id)
        payload = request.get_json(force=True)
        if 'success' in payload:
            val = payload.get('success')
            if val is not None and not isinstance(val, bool):
                return jsonify({'error': 'success must be boolean or null'}), 400
            run.success = val
        if 'score' in payload:
            try:
                score = float(payload.get('score')) if payload.get('score') is not None else None
            except ValueError:
                return jsonify({'error': 'score must be a number'}), 400
            run.score = score
        if 'notes' in payload:
            run.notes = payload.get('notes')
        db.session.commit()
        return jsonify({'ok': True, 'id': run.id, 'success': run.success, 'score': run.score, 'notes': run.notes})

    @app.route('/api/metrics/prompt/<int:prompt_id>', methods=['GET'])
    def api_prompt_metrics(prompt_id):
        Prompt.query.get_or_404(prompt_id)
        metrics = compute_prompt_metrics(prompt_id)
        return jsonify(metrics)

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '5000')), debug=True)



@app.route('/health', methods=['GET'])
def _auto_stub_health():
    return 'Auto-generated stub for /health', 200
