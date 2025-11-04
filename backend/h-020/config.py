import os
from dataclasses import dataclass

@dataclass
class Config:
    # Notion
    notion_token: str | None
    notion_version: str
    notion_parent_page_id: str | None

    # Confluence
    confluence_base_url: str | None
    confluence_username: str | None
    confluence_api_token: str | None

    # Internal Filesystem Wiki
    file_wiki_dir: str

    # Mapping store file
    mappings_file: str

    @staticmethod
    def from_env() -> 'Config':
        return Config(
            notion_token=os.environ.get('NOTION_TOKEN'),
            notion_version=os.environ.get('NOTION_VERSION', '2022-06-28'),
            notion_parent_page_id=os.environ.get('NOTION_PARENT_PAGE_ID'),
            confluence_base_url=os.environ.get('CONFLUENCE_BASE_URL'),
            confluence_username=os.environ.get('CONFLUENCE_USERNAME'),
            confluence_api_token=os.environ.get('CONFLUENCE_API_TOKEN'),
            file_wiki_dir=os.environ.get('FILE_WIKI_DIR', 'wiki_data'),
            mappings_file=os.environ.get('MAPPINGS_FILE', 'data/mappings.json'),
        )

