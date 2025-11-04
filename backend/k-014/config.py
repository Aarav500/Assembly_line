import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")
    GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
    WORKSPACES_DIR = os.environ.get("WORKSPACES_DIR", os.path.abspath(os.path.join(os.getcwd(), "workspaces")))
    # Set a reasonable timeout for network operations
    HTTP_TIMEOUT = float(os.environ.get("HTTP_TIMEOUT", 20))

