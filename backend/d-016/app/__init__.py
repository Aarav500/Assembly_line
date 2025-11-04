from flask import Flask


def create_app() -> Flask:
    app = Flask(__name__)

    from .routes import bp as routes_bp

    app.register_blueprint(routes_bp)

    @app.route('/health')
    def health():
        return {'status': 'ok'}

    return app

