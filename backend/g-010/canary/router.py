import random
from typing import Optional


class TrafficRouter:
    def __init__(self, controller, models: dict):
        self.controller = controller
        self.models = models

    def choose_version(self, force_version: Optional[str] = None, user_id: Optional[str] = None) -> str:
        state = self.controller.get_state()
        stable = state.get("stable_version")
        canary = state.get("canary_version")
        weight = float(state.get("canary_weight", 0.0))

        if force_version:
            return force_version if force_version in self.models else stable

        if not canary or weight <= 0.0:
            return stable

        # Optionally make a simple sticky decision per user by hashing user_id
        if user_id:
            # Deterministic fraction in [0,1)
            frac = (hash(user_id) % 10_000) / 10_000.0
            return canary if frac < weight else stable

        # Random split
        return canary if random.random() < weight else stable

