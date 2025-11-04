import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, jsonify, render_template, request


def create_app():
    app = Flask(__name__, static_folder='static', template_folder='templates')

    @app.route('/')
    def index():
        try:
            default_path = request.args.get('path', os.path.abspath('example_project'))
            return render_template('index.html', default_path=default_path)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/health')
    def health():
        return jsonify({'status': 'ok'})

    @app.route('/api/analyze')
    def analyze():
        try:
            root_path = request.args.get('path')
            include_externals = request.args.get('include_externals', 'false').lower() == 'true'
            include_tests = request.args.get('include_tests', 'false').lower() == 'true'
            exclude_raw = request.args.get('exclude', '')
            if not root_path:
                root_path = os.getcwd()
            root_path = os.path.abspath(root_path)
            if not os.path.exists(root_path):
                return jsonify({'error': f'Path not found: {root_path}'}), 400

            default_excludes = [
                'venv', '.venv', 'env', '.env', '.git', 'node_modules', 'dist', 'build',
                '__pycache__', 'site-packages', '.mypy_cache', '.pytest_cache', '.tox', '.ruff_cache'
            ]
            if not include_tests:
                default_excludes += ['tests', 'test', 'testing']
            extra_excludes = [e.strip() for e in exclude_raw.split(',') if e.strip()]
            excludes = list(dict.fromkeys(default_excludes + extra_excludes))

            from utils.analyzer import CodebaseAnalyzer
            analyzer = CodebaseAnalyzer(root_path, exclude_patterns=excludes)
            result = analyzer.analyze(include_externals=include_externals)
            return jsonify(result)
        except FileNotFoundError as e:
            return jsonify({'error': f'File or directory not found: {str(e)}'}), 404
        except PermissionError as e:
            return jsonify({'error': f'Permission denied: {str(e)}'}), 403
        except Exception as e:
            return jsonify({'error': f'Analysis failed: {str(e)}'}), 500

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)