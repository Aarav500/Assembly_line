import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask
from config import Config
from database import db
from models import User, Profile
from profiles import seed_default_profiles
from routes.profiles import profiles_bp
from routes.users import users_bp
from routes.chat import chat_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    with app.app_context():
        db.create_all()
        seed_default_profiles()

    app.register_blueprint(profiles_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(chat_bp)

    @app.route('/')
    def index():
        return {
            "status": "ok",
            "message": "AI preference profiles service running",
            "endpoints": [
                "/profiles",
                "/users",
                "/chat"
            ]
        }

    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)



@app.route('/health', methods=['GET'])
def _auto_stub_health():
    return 'Auto-generated stub for /health', 200


@app.route('/profiles/user1', methods=['GET', 'POST'])
def _auto_stub_profiles_user1():
    return 'Auto-generated stub for /profiles/user1', 200


@app.route('/profiles/user2', methods=['POST'])
def _auto_stub_profiles_user2():
    return 'Auto-generated stub for /profiles/user2', 200
