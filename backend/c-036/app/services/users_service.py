from __future__ import annotations
from typing import List, Dict, Any, Optional
from flask import current_app
import itertools


class UsersService:
    def __init__(self):
        self._users: List[Dict[str, Any]] = []
        self._id_seq = itertools.count(1)

    def seed(self):
        if not self._users:
            for u in current_app.config.get('SEED_USERS', []):
                self._users.append({
                    "id": next(self._id_seq),
                    "first_name": u.get("first_name"),
                    "last_name": u.get("last_name"),
                    "email": u.get("email")
                })

    def list_users(self) -> List[Dict[str, Any]]:
        self.seed()
        return list(self._users)

    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        self.seed()
        return next((u for u in self._users if u['id'] == user_id), None)

    def create_user(self, data: Dict[str, Any]) -> Dict[str, Any]:
        self.seed()
        new_user = {
            "id": next(self._id_seq),
            "first_name": data.get("first_name"),
            "last_name": data.get("last_name"),
            "email": data.get("email")
        }
        self._users.append(new_user)
        return new_user

    def update_user(self, user_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        self.seed()
        user = self.get_user(user_id)
        if not user:
            return None
        for field in ("first_name", "last_name", "email"):
            if field in data:
                user[field] = data[field]
        return user


# Simple app-global service instance
_users_service: UsersService | None = None


def users_service() -> UsersService:
    global _users_service
    if _users_service is None:
        _users_service = UsersService()
    return _users_service

