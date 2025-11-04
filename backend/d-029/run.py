import os
from dotenv import load_dotenv
from app.app import create_app

# Load local .env if present
load_dotenv()

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))

