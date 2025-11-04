import os

# Local desired state path (used if no GitHub repo configured)
LOCAL_DESIRED_PATH = os.environ.get('LOCAL_DESIRED_PATH', 'desired/desired_state.json')

# Data directory for caching last drift, actual state, etc.
DATA_DIR = os.environ.get('DATA_DIR', 'data')

# Default drift handling mode
# - 'enforce_desired': suggest changing the environment to match desired
# - 'update_desired': suggest changing desired to match actual (and can open PR)
DEFAULT_MODE = os.environ.get('DEFAULT_MODE', 'enforce_desired')

# GitHub configuration
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
GITHUB_REPO = os.environ.get('GITHUB_REPO')  # format: owner/repo
GITHUB_BASE_BRANCH = os.environ.get('GITHUB_BASE_BRANCH', 'main')
GITHUB_DESIRED_PATH = os.environ.get('GITHUB_DESIRED_PATH', 'desired/desired_state.json')

# Alerts (optional)
SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL')

