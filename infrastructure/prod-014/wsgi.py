import os
from app import create_app

app = create_app(env=os.getenv("APP_ENV", "development"), config_dir=os.getenv("APP_CONFIG_DIR"))

