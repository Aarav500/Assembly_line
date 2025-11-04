import os
from flask import Blueprint, jsonify, request, current_app
from sqlalchemy import create_engine
from .analyzer import analyze
from .migration_gen import generate_alembic_script

bp = Blueprint('routes', __name__)


@bp.get("/health")
def health():
    return jsonify({"status": "ok", "app": current_app.config.get('APP_NAME', 'MigrationAssist')})


@bp.post("/analyze")
def analyze_endpoint():
    payload = request.get_json(silent=True) or {}
    database_url = payload.get('database_url') or current_app.config['DATABASE_URL']
    models_module = payload.get('models_module') or current_app.config['DEFAULT_MODELS_MODULE']
    include_sql = bool(payload.get('include_sql', current_app.config['INCLUDE_SQL']))
    include_alembic_ops = bool(payload.get('include_alembic_ops', current_app.config['INCLUDE_ALEMBIC_OPS']))

    try:
        result = analyze(database_url=database_url, models_module=models_module, include_sql=include_sql, include_alembic_ops=include_alembic_ops)
        return jsonify({
            'ok': True,
            'engine': result.get('engine_dialect'),
            'summary': result.get('summary'),
            'tables': result.get('tables'),
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400


@bp.post("/generate-migration")
def generate_migration():
    payload = request.get_json(silent=True) or {}
    database_url = payload.get('database_url') or current_app.config['DATABASE_URL']
    models_module = payload.get('models_module') or current_app.config['DEFAULT_MODELS_MODULE']
    message = payload.get('message', 'auto_suggested')

    try:
        plan = analyze(database_url=database_url, models_module=models_module, include_sql=True, include_alembic_ops=False)
        script_info = generate_alembic_script(plan, message=message)
        return jsonify({
            'ok': True,
            'filename': script_info['filename'],
            'content': script_info['content'],
            'summary': plan.get('summary'),
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400

