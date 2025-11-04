import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
    FIGMA_TOKEN = os.environ.get('FIGMA_TOKEN', '')

