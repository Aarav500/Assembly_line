import os
from dotenv import load_dotenv
from app.web.api import create_app

if __name__ == "__main__":
    load_dotenv()
    app = create_app()
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_PORT", "8000"))
    app.run(host=host, port=port)
