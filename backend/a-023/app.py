import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask
from db import Base, engine
from routes import bp
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# Initialize DB schema
Base.metadata.create_all(bind=engine)

# Register API
app.register_blueprint(bp)

@app.route('/')
def index():
    return {'status': 'ok', 'message': 'Audit Trail Service', 'endpoints': ['/projects', '/projects/<id>/audit']}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=Config.DEBUG)



def create_app():
    return app


@app.route('/health')
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": time.time()}

@app.route('/ready')
def readiness_check():
    """Readiness check endpoint"""
    return {"status": "ready"}
