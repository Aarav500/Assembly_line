from flask import Flask
from .api.routes import api_bp
from .util import helper_a


def create_app():
    app = Flask(__name__)
    app.register_blueprint(api_bp, url_prefix='/a')
    helper_a()
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(port=5001)

