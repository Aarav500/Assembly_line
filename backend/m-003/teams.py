import json
import os
from typing import Dict, List, Optional

from utils import normalize_owner_id


class TeamDirectory:
    def __init__(self, teams: Dict[str, List[str]], source_path: Optional[str]):
        # keys: '@org/team' (normalized), values: list of members (original strings)
        self._teams = {normalize_owner_id(k): v for k, v in teams.items()}
        self.source_path = source_path

    @staticmethod
    def load(repo_path: str, teams_path: Optional[str] = None) -> "TeamDirectory":
        locations = []
        if teams_path:
            locations.append(teams_path)
        locations.append(os.path.join(repo_path, "teams.json"))
        locations.append(os.path.join(repo_path, ".github", "teams.json"))

        for path in locations:
            if path and os.path.isfile(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            return TeamDirectory(data, path)
                except Exception:
                    pass
        return TeamDirectory({}, None)

    def expand_owners(self, owners: List[str]) -> List[str]:
        expanded: List[str] = []
        for owner in owners:
            nid = normalize_owner_id(owner)
            if nid in self._teams:
                expanded.extend(self._teams[nid])
            else:
                expanded.append(owner)
        return expanded

