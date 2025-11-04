import os

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SCHEDULER_ENABLED = os.getenv('SCHEDULER_ENABLED', '1') == '1'
    COST_CURRENCY = os.getenv('COST_CURRENCY', 'USD')
    JSON_SORT_KEYS = False

