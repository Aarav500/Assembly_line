import os
import yaml
from typing import Dict

class PolicyService:
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = config_path
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        if not os.path.exists(self.config_path):
            self.save({})

    def load(self) -> Dict:
        with open(self.config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data

    def save(self, data: Dict):
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False)

