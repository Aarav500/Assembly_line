import os
import threading
import time
from flask import Flask
from .config import Config
from .database import db, init_db
from .routes import api_bp
from .detector import Detector

_detector_thread = None


def _start_detector(app: Flask):
    global _detector_thread
    if _detector_thread and _detector_thread.is_alive():
        return

    detector = Detector(app)

    def run():
        with app.app_context():
            detector.run_forever()

    t = threading.Thread(target=run, name="regression-detector", daemon=True)
    t.start()
    _detector_thread = t


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config())

    init_db(app)

    app.register_blueprint(api_bp)

    @app.get("/health")
    def health():
        return {"status": "ok", "detector_enabled": app.config.get("DETECTOR_ENABLED", True)}, 200

    if app.config.get("DETECTOR_ENABLED", True):
        # Delay start to allow DB migrations/creation
        threading.Timer(1.0, _start_detector, args=(app,)).start()

    return app

