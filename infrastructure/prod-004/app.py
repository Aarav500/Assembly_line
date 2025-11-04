import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
from flask import Flask
from blueprints.api import api_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object('config')

    # Logging
    logging.basicConfig(level=logging.INFO)

    # Ensure JSON responses are not sorted to preserve field order for versioned payloads
    app.config['JSON_SORT_KEYS'] = False

    app.register_blueprint(api_bp)

    @app.route('/')
    def index():
        return {
            'name': app.config.get('API_NAME', 'myapi'),
            'latest_version': app.config.get('LATEST_VERSION'),
            'supported_versions': app.config.get('SUPPORTED_VERSIONS'),
        }

    return app


app = create_app()

if __name__ == '__main__':
    # For local development
    app.run(host='0.0.0.0', port=5000, debug=True)

