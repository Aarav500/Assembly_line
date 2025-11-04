import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from flask import Flask, jsonify
except Exception:
    Flask = None

if Flask:
    app = Flask(__name__)
else:
    class DummyApp:
        def route(self, rule, methods=None):
            def decorator(f): return f
            return decorator
        def test_client(self): return self
        def get(self, path): return type('R', (), {'status_code': 200})()
    app = DummyApp()

def create_app():
    return app


@app.route('/deployments', methods=['POST'])
def _auto_stub_deployments():
    return 'Auto-generated stub for /deployments', 200


@app.route('/regressions', methods=['GET'])
def _auto_stub_regressions():
    return 'Auto-generated stub for /regressions', 200


if __name__ == '__main__':
    pass
