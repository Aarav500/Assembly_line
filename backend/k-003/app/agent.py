from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from typing import Optional
from flask import current_app


@dataclass
class AgentState:
    mode: str = "normal"  # "normal" | "maintenance"
    active_window_id: Optional[int] = None
    end_at: Optional[datetime] = None


class AgentManager:
    def __init__(self):
        self._state = AgentState()
        self._lock = RLock()

    def get_state(self) -> AgentState:
        with self._lock:
            return AgentState(self._state.mode, self._state.active_window_id, self._state.end_at)

    def enter_maintenance(self, window_id: int, end_at: datetime) -> bool:
        with self._lock:
            if self._state.mode == "maintenance" and self._state.active_window_id == window_id:
                # extend end if later
                if self._state.end_at and end_at > self._state.end_at:
                    self._state.end_at = end_at
                return False
            self._state.mode = "maintenance"
            self._state.active_window_id = window_id
            self._state.end_at = end_at
            current_app.logger.info(f"Entered maintenance mode for window {window_id} until {end_at.isoformat()}")
            return True

    def exit_maintenance(self, window_id: int | None = None) -> bool:
        with self._lock:
            if self._state.mode != "maintenance":
                return False
            if window_id is not None and self._state.active_window_id != window_id:
                return False
            current_app.logger.info("Exiting maintenance mode")
            self._state = AgentState()
            return True

    def retraining_allowed(self) -> bool:
        with self._lock:
            if self._state.mode == "maintenance" and not current_app.config.get("RETRAIN_INSIDE_MAINTENANCE", False):
                return False
            return True


agent_manager = AgentManager()

