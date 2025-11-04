import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, jsonify
from redis import Redis
from dotenv import load_dotenv
from config import Config
from rate_limit_middleware import RateLimitMiddleware

load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)

# Redis client
redis_client = Redis.from_url(app.config["REDIS_URL"], decode_responses=False)

# Initialize middleware
rl = RateLimitMiddleware(app, redis_client=redis_client)

@app.get("/health")
def health():
    return jsonify({"status": "ok"})

@app.get("/")
def index():
    return jsonify({"message": "Hello, world!"})

@app.get("/protected")
def protected():
    return jsonify({"message": "This route is rate-limited."})

@app.get("/admin/ban/<ip>")
def admin_ban(ip):
    # Example admin endpoint for manual ban (do NOT expose in production)
    dur = int(os.getenv("RL_BAN_DURATION", "900"))
    key_prefix = app.config.get("RL_REDIS_KEY_PREFIX", "rl")
    redis_client.setex(f"{key_prefix}:ban:{ip}", dur, b"1")
    return jsonify({"banned": ip, "duration": dur})

@app.get("/admin/unban/<ip>")
def admin_unban(ip):
    key_prefix = app.config.get("RL_REDIS_KEY_PREFIX", "rl")
    redis_client.delete(f"{key_prefix}:ban:{ip}")
    return jsonify({"unbanned": ip})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))



def create_app():
    return app
