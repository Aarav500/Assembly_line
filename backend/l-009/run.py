from app import create_app

app = create_app()

if __name__ == "__main__":
    # For development only. In production use a WSGI server.
    app.run(host=app.config.get("HOST", "0.0.0.0"), port=app.config.get("PORT", 5000))

