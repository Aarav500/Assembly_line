from typing import Dict, List
from connectors.base import BaseConnector
from connectors.notion import NotionConnector
from connectors.figma import FigmaConnector
from connectors.jira import JiraConnector
from connectors.slack import SlackConnector
from connectors.s3 import S3Connector
from connectors.database import DatabaseConnector


class PluginManager:
    def __init__(self, config):
        self.config = config
        self._connectors: Dict[str, BaseConnector] = {}
        self._load_connectors()

    def _load_connectors(self):
        candidates: List[BaseConnector] = [
            NotionConnector(self.config),
            FigmaConnector(self.config),
            JiraConnector(self.config),
            SlackConnector(self.config),
            S3Connector(self.config),
            DatabaseConnector(self.config),
        ]
        for c in candidates:
            self._connectors[c.slug] = c

    @property
    def connectors(self) -> Dict[str, BaseConnector]:
        return self._connectors

    def get(self, slug: str) -> BaseConnector:
        return self._connectors.get(slug)

    def list_metadata(self):
        metas = []
        for slug, conn in self._connectors.items():
            metas.append({
                "slug": slug,
                "name": conn.name,
                "enabled": conn.enabled,
                "operations": conn.available_operations(),
                "health": conn.safe_health(),
            })
        return metas

