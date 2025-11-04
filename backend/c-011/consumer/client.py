import requests


class ProviderClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def get_user(self, user_id: int):
        resp = requests.get(f"{self.base_url}/api/users/{user_id}", timeout=2)
        resp.raise_for_status()
        return resp.json()

