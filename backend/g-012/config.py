import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    DRIFT_WINDOW_SIZE = int(os.getenv('DRIFT_WINDOW_SIZE', '500'))
    DRIFT_CHECK_INTERVAL_SECONDS = int(os.getenv('DRIFT_CHECK_INTERVAL_SECONDS', '60'))
    NUM_BINS = int(os.getenv('NUM_BINS', '10'))

    PSI_THRESHOLD = float(os.getenv('PSI_THRESHOLD', '0.2'))  # high severity
    PSI_THRESHOLD_WARN = float(os.getenv('PSI_THRESHOLD_WARN', '0.1'))  # warning severity
    CAT_P_THRESHOLD = float(os.getenv('CAT_P_THRESHOLD', '0.01'))
    OUTPUT_PSI_THRESHOLD = float(os.getenv('OUTPUT_PSI_THRESHOLD', '0.2'))

    ALERT_COOLDOWN_SECONDS = int(os.getenv('ALERT_COOLDOWN_SECONDS', '600'))

    ENABLE_SLACK = os.getenv('ENABLE_SLACK', 'false').lower() == 'true'
    SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL', '')

    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

    BASELINE_PATH = os.getenv('BASELINE_PATH', 'data/baseline.json')

