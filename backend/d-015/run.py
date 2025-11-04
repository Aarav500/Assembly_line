import logging
from app import create_app
from jobs.scheduler import init_scheduler

app = create_app()
init_scheduler(app)

if __name__ == "__main__":
    logging.basicConfig(level=getattr(logging, app.config.get("LOG_LEVEL", "INFO")))
    app.run(host=app.config["APP_HOST"], port=app.config["APP_PORT"]) 

