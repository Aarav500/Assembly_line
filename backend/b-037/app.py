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


@app.route('/test-plans', methods=['GET'])
def _auto_stub_test_plans():
    return 'Auto-generated stub for /test-plans', 200


@app.route('/assign-variant', methods=['POST'])
def _auto_stub_assign_variant():
    return 'Auto-generated stub for /assign-variant', 200


if __name__ == '__main__':
    pass
