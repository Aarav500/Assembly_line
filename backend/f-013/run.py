from app import app
from utils import load_config

if __name__ == "__main__":
    cfg = load_config()
    host = (cfg.get("app", {}) or {}).get("host", "0.0.0.0")
    port = int((cfg.get("app", {}) or {}).get("port", 8080))
    app.run(host=host, port=port)

