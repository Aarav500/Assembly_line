from app import create_app

app = create_app()

if __name__ == "__main__":
    # For local debugging only; prefer `flask run` in production setups
    app.run(host="0.0.0.0", port=5000, debug=True)

