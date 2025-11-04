import threading
import time
from typing import Dict, Tuple, Optional


class Orchestrator:
    def __init__(self, blue_url: str, green_url: str, *,
                 strategy: str = "blue_green",
                 active: str = "blue",
                 blue_weight: int = 100,
                 green_weight: int = 0) -> None:
        self._lock = threading.RLock()
        self._state = {
            "strategy": strategy,  # blue_green | canary
            "blue": {"url": blue_url, "healthy": True, "name": "blue"},
            "green": {"url": green_url, "healthy": True, "name": "green"},
            "active": active,  # for blue_green
            "weights": {"blue": int(blue_weight), "green": int(green_weight)}  # for canary, sum ideally 100
        }

    # ----- State helpers -----
    def get_status(self) -> Dict:
        with self._lock:
            return {
                "strategy": self._state["strategy"],
                "active": self._state["active"],
                "weights": dict(self._state["weights"]),
                "blue": {"url": self._state["blue"]["url"], "healthy": self._state["blue"]["healthy"]},
                "green": {"url": self._state["green"]["url"], "healthy": self._state["green"]["healthy"]},
                "timestamp": int(time.time())
            }

    def set_strategy(self, strategy: str) -> Dict:
        if strategy not in ("blue_green", "canary"):
            raise ValueError("strategy must be 'blue_green' or 'canary'")
        with self._lock:
            self._state["strategy"] = strategy
            return self.get_status()

    def activate(self, color: str) -> Dict:
        if color not in ("blue", "green"):
            raise ValueError("active must be 'blue' or 'green'")
        with self._lock:
            self._state["active"] = color
            return self.get_status()

    def set_weights(self, blue: int, green: int, normalize: bool = True) -> Dict:
        if blue < 0 or green < 0:
            raise ValueError("weights cannot be negative")
        with self._lock:
            if normalize:
                total = blue + green
                if total == 0:
                    # default to 100/0
                    blue_n, green_n = 100, 0
                else:
                    blue_n = round(blue * 100 / total)
                    green_n = 100 - blue_n
                self._state["weights"] = {"blue": blue_n, "green": green_n}
            else:
                if blue + green != 100:
                    raise ValueError("weights must sum to 100 when normalize=False")
                self._state["weights"] = {"blue": blue, "green": green}
            return self.get_status()

    def shift_canary(self, delta: int, towards: str = "green") -> Dict:
        if towards not in ("green", "blue"):
            raise ValueError("towards must be 'green' or 'blue'")
        with self._lock:
            w = dict(self._state["weights"])  # copy
            if towards == "green":
                w["green"] = min(100, max(0, w["green"] + delta))
                w["blue"] = 100 - w["green"]
            else:
                w["blue"] = min(100, max(0, w["blue"] + delta))
                w["green"] = 100 - w["blue"]
            self._state["weights"] = w
            return self.get_status()

    def update_health(self, color: str, healthy: bool) -> None:
        if color not in ("blue", "green"):
            return
        with self._lock:
            self._state[color]["healthy"] = bool(healthy)

    # ----- Choosing targets -----
    def choose(self, session_hash: Optional[int] = None) -> Tuple[str, str]:
        """
        Returns a tuple (color, url) for the selected upstream based on the current strategy.
        session_hash: an int between 0-100 or a larger int; will be normalized for weighted selection.
        """
        with self._lock:
            strategy = self._state["strategy"]
            active = self._state["active"]
            blue = self._state["blue"]
            green = self._state["green"]
            weights = self._state["weights"]

        # Prefer healthy services. If selected is unhealthy, fallback to the other if healthy.
        def is_healthy(color: str) -> bool:
            return blue["healthy"] if color == "blue" else green["healthy"]

        def url_of(color: str) -> str:
            return blue["url"] if color == "blue" else green["url"]

        if strategy == "blue_green":
            chosen = active
            if not is_healthy(chosen) and is_healthy("green" if chosen == "blue" else "blue"):
                chosen = "green" if chosen == "blue" else "blue"
            return chosen, url_of(chosen)

        # strategy == "canary"
        # map a hash to 0..99 and compare to weight threshold.
        threshold_green = int(weights.get("green", 0))
        # Normalize hash to 0..99
        if session_hash is None:
            # Use current time nanoseconds as a pseudo-random fallback
            session_hash = int(time.time_ns())
        bucket = abs(session_hash) % 100
        chosen = "green" if bucket < threshold_green else "blue"

        # Health-aware fallback
        if not is_healthy(chosen) and is_healthy("green" if chosen == "blue" else "blue"):
            chosen = "green" if chosen == "blue" else "blue"
        return chosen, url_of(chosen)

