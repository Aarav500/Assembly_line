import os
from flask import Flask
from .routes import bp as main_bp

def create_app() -> Flask:
    app = Flask(__name__)
    app.config['APP_VERSION'] = os.getenv('APP_VERSION', '0.1.0')

    # Register blueprints
    app.register_blueprint(main_bp)

    @app.get('/healthz')
    def healthz():
        return {'status': 'ok'}, 200

    @app.get('/readyz')
    def readyz():
        # Insert readiness checks here (db, cache, etc.)
        return {'status': 'ready'}, 200

    @app.get('/version')
    def version():
        return {
            'version': app.config.get('APP_VERSION', ''),
            'build': os.getenv('BUILD_NUMBER', ''),
            'commit': os.getenv('GIT_SHA', ''),
        }, 200

    return app

