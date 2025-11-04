import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask

app = Flask(__name__)

@app.route('/')
def index():
    return {'status': 'ok', 'message': 'API is running'}

@app.route('/health')
def health():
    return {'status': 'healthy'}

if __name__ == '__main__':
    app.run(debug=True)


def create_app():
    return app
