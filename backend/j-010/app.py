import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask
from api import api_bp

def create_app():
    app = Flask(__name__)
    app.register_blueprint(api_bp, url_prefix="/api")
    return app



@app.route('/analyze', methods=['POST'])
def _auto_stub_analyze():
    return 'Auto-generated stub for /analyze', 200


@app.route('/health', methods=['GET'])
def _auto_stub_health():
    return 'Auto-generated stub for /health', 200
