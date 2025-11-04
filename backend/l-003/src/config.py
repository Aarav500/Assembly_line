import os

def load_config():
    cfg = {}

    # Flask / Server
    cfg["HOST"] = os.getenv("HOST", "0.0.0.0")
    cfg["PORT"] = int(os.getenv("PORT", "5000"))
    cfg["DEBUG"] = os.getenv("DEBUG", "false").lower() == "true"
    cfg["CORS_ORIGINS"] = os.getenv("CORS_ORIGINS", "*")

    # Notion
    cfg["NOTION_TOKEN"] = os.getenv("NOTION_TOKEN")
    cfg["NOTION_VERSION"] = os.getenv("NOTION_VERSION", "2022-06-28")

    # Figma
    cfg["FIGMA_TOKEN"] = os.getenv("FIGMA_TOKEN")

    # Jira
    cfg["JIRA_BASE_URL"] = os.getenv("JIRA_BASE_URL")
    cfg["JIRA_EMAIL"] = os.getenv("JIRA_EMAIL")
    cfg["JIRA_API_TOKEN"] = os.getenv("JIRA_API_TOKEN")

    # Slack
    cfg["SLACK_BOT_TOKEN"] = os.getenv("SLACK_BOT_TOKEN")

    # S3
    cfg["AWS_ACCESS_KEY_ID"] = os.getenv("AWS_ACCESS_KEY_ID")
    cfg["AWS_SECRET_ACCESS_KEY"] = os.getenv("AWS_SECRET_ACCESS_KEY")
    cfg["AWS_REGION"] = os.getenv("AWS_REGION")
    cfg["S3_BUCKET"] = os.getenv("S3_BUCKET")

    # Database
    cfg["DATABASE_URL"] = os.getenv("DATABASE_URL", "sqlite:///./example.db")
    cfg["ALLOW_DB_RAW_SELECT"] = os.getenv("ALLOW_DB_RAW_SELECT", "false").lower() == "true"

    return cfg

