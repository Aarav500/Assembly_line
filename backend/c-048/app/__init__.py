from flask import Flask


def create_app():
    app = Flask(__name__)

    from .routes import bp as generator_bp
    app.register_blueprint(generator_bp)

    @app.route('/health', methods=['GET'])
    def health():
        return {'status': 'ok'}, 200

    return app

