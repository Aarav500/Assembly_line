import os


class Config:
    # Max upload size: 25 MB
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 25 * 1024 * 1024))

    # Default policy directory
    POLICY_DIR = os.getenv("POLICY_DIR", os.path.abspath(os.path.join(os.getcwd(), "policies")))

    # Temporary base directory for uploads
    TEMP_BASE_DIR = os.getenv("TEMP_BASE_DIR", os.path.abspath(os.path.join(os.getcwd(), ".tmp")))

    # Allowed file extensions for scanning
    ALLOWED_EXTENSIONS = set(
        (os.getenv("ALLOWED_EXTENSIONS", "yaml,yml,json,tf,tf.json,tfvars,hcl")).split(",")
    )

    # Whether to treat warnings as failures
    FAIL_ON_WARN = os.getenv("FAIL_ON_WARN", "false").lower() in ("1", "true", "yes")

    # Conftest binary path (falls back to PATH lookup)
    CONFTEST_BIN = os.getenv("CONFTEST_BIN", "conftest")

