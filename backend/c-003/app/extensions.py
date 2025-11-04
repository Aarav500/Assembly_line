import logging
from flask_cors import CORS

cors = CORS()


def register_extensions(app):
    # CORS
    origins = app.config.get("CORS_ORIGINS", "*")
    cors.init_app(
        app,
        resources={
            r"/api/*": {"origins": origins},
            r"/health*": {"origins": origins},
            r"/*": {"origins": origins},
        },
        supports_credentials=True,
    )

    # Logging
    level_name = (app.config.get("LOG_LEVEL") or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    if not app.logger.handlers:
        logging.basicConfig(level=level)
    app.logger.setLevel(level)

    return app

