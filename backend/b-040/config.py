import os
from dataclasses import dataclass


@dataclass
class Settings:
    NOTION_API_TOKEN: str
    NOTION_PARENT_PAGE_ID: str
    NOTION_DATABASE_ID: str
    NOTION_TITLE_PROPERTY: str
    GOOGLE_SERVICE_ACCOUNT_FILE: str
    GITHUB_TOKEN: str
    GITHUB_REPO: str
    EXPORT_OUTPUT_DIR: str


def get_settings() -> Settings:
    return Settings(
        NOTION_API_TOKEN=os.getenv('NOTION_API_TOKEN', ''),
        NOTION_PARENT_PAGE_ID=os.getenv('NOTION_PARENT_PAGE_ID', ''),
        NOTION_DATABASE_ID=os.getenv('NOTION_DATABASE_ID', ''),
        NOTION_TITLE_PROPERTY=os.getenv('NOTION_TITLE_PROPERTY', 'Name'),
        GOOGLE_SERVICE_ACCOUNT_FILE=os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE', ''),
        GITHUB_TOKEN=os.getenv('GITHUB_TOKEN', ''),
        GITHUB_REPO=os.getenv('GITHUB_REPO', ''),
        EXPORT_OUTPUT_DIR=os.getenv('EXPORT_OUTPUT_DIR', 'exports'),
    )

