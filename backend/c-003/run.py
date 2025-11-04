from dotenv import load_dotenv
from app import create_app

if __name__ == "__main__":
    load_dotenv()
    app = create_app("development")
    app.run(host=app.config["HOST"], port=app.config["PORT"], debug=True)

