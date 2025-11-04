from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_compress import Compress
from .routes import api_bp
from .utils import request_timer_before, request_timer_after, add_common_headers

def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_mapping({
        "JSONIFY_PRETTYPRINT_REGULAR": False,
        "SEND_FILE_MAX_AGE_DEFAULT": 3600,
        "ETAG_STRONG": False,
    })

    # Behind proxies/CDNs
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    # Compression for faster edge delivery
    Compress(app)

    # Timing and headers for low-latency hints
    app.before_request(request_timer_before)
    app.after_request(add_common_headers)
    app.after_request(request_timer_after)

    # Routes
    app.register_blueprint(api_bp, url_prefix="/")

    return app

