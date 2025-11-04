"""
Entrypoint script for running the Flask development server.

Developer explanation:
- This file is intentionally small. It imports the application factory from app/__init__.py,
  creates the app instance, and runs the built-in development server if executed directly.
- For production deployments, prefer a WSGI server (e.g., gunicorn, uWSGI) and point it
  to 'app:create_app()' or to the 'app' variable defined below.
"""

from app import create_app

# Create the Flask app instance using the application factory.
# If FLASK_ENV or APP_ENV is set, the factory will choose the appropriate config.
app = create_app()

if __name__ == "__main__":
    # Running with Flask's built-in server is convenient for development.
    # Do not use this for production.
    app.run(host="127.0.0.1", port=5000, debug=app.config.get("DEBUG", False))

