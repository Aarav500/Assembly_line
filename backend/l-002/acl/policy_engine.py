import yaml
from fnmatch import fnmatch
from typing import Any, Dict, List, Optional


class PolicyEngine:
    def __init__(self, policy_file: str):
        self.policy_file = policy_file
        self.policies = {"roles": {}, "users": {}}
        self.api_key_index = {}
        self.load()

    def load(self):
        with open(self.policy_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        self.policies['roles'] = data.get('roles', {})
        self.policies['users'] = data.get('users', {})
        # Build api_key index
        self.api_key_index = {}
        for uname, u in self.policies['users'].items():
            api_key = u.get('api_key')
            if api_key:
                self.api_key_index[api_key] = {
                    'name': uname,
                    'roles': u.get('roles', []),
                    'metadata': u.get('metadata', {}),
                    'api_key': api_key,
                }

    def reload(self):
        self.load()

    def get_user_by_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        return self.api_key_index.get(api_key)

    def is_allowed(self, user: Dict[str, Any], action: str, path: str) -> bool:
        # Deny by default if no user or no roles
        if not user:
            return False
        roles = user.get('roles', [])
        # Aggregate allow and deny rules from all roles
        allow_rules: List[Dict[str, Any]] = []
        deny_rules: List[Dict[str, Any]] = []
        for role in roles:
            rdef = self.policies['roles'].get(role, {})
            allow_rules.extend(rdef.get('allow', []) or [])
            deny_rules.extend(rdef.get('deny', []) or [])
        # Evaluate deny first
        for rule in deny_rules:
            if self._match_rule(rule, action, path):
                return False
        # Evaluate allows
        for rule in allow_rules:
            if self._match_rule(rule, action, path):
                return True
        return False

    @staticmethod
    def _match_rule(rule: Dict[str, Any], action: str, path: str) -> bool:
        actions = rule.get('actions', [])
        patt = rule.get('path', '')
        if actions and action not in actions:
            return False
        if patt and not fnmatch(path, patt):
            return False
        return True

