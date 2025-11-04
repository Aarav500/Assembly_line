import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from werkzeug.utils import secure_filename

from analysis import analyze_file
from config import Config
from network_guard import activate_privacy_mode


def create_app():
    app = Flask(__name__, instance_relative_config=True, static_folder='static', template_folder='templates')
    app.config.from_object(Config)

    # Ensure instance and upload folders exist
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Activate privacy mode guard if enabled
    if app.config.get('PRIVACY_MODE', True):
        activate_privacy_mode()

    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

    @app.route('/')
    def index():
        return render_template('index.html', privacy_mode=app.config.get('PRIVACY_MODE', True),
                               max_size_mb=app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024),
                               allowed_ext=', '.join(sorted(app.config['ALLOWED_EXTENSIONS'])))

    @app.route('/analyze', methods=['POST'])
    def analyze():
        if 'file' not in request.files:
            flash('No file part in the request')
            return redirect(url_for('index'))
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(url_for('index'))
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(save_path)
            try:
                result = analyze_file(save_path)
            except Exception as e:
                flash(f'Analysis failed: {e}')
                return redirect(url_for('index'))
            return render_template('result.html', result=result, filename=filename, privacy_mode=app.config.get('PRIVACY_MODE', True))
        else:
            flash('Unsupported file type')
            return redirect(url_for('index'))

    @app.route('/api/analyze', methods=['POST'])
    def api_analyze():
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "Empty filename"}), 400
        filename = secure_filename(file.filename)
        if not allowed_file(filename):
            return jsonify({"error": "Unsupported file type"}), 400
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(save_path)
        try:
            result = analyze_file(save_path)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        return jsonify({
            "filename": filename,
            "privacy_mode": app.config.get('PRIVACY_MODE', True),
            "result": result
        })

    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({"status": "ok", "privacy_mode": app.config.get('PRIVACY_MODE', True)})

    return app


if __name__ == '__main__':
    app = create_app()
    # Bind only to localhost to keep everything local
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT', 5000)), debug=False)

