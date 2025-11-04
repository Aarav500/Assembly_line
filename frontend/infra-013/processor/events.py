import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Callable


@dataclass
class Event:
    id: str
    type: str
    payload: Dict[str, Any]
    received_at: float


class EventProcessor:
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self._handlers: Dict[str, Callable[[Event], None]] = {
            "user.created": self._handle_user_created,
            "order.created": self._handle_order_created,
            "event.echo": self._handle_echo,
        }

    def process(self, event: Event) -> None:
        # Simulate failure on demand for testing retry logic
        if event.payload.get("simulate_failure"):
            raise RuntimeError("simulated failure as requested")

        handler = self._handlers.get(event.type)
        if not handler:
            self.logger.warning(
                "no handler for event type; ignoring",
                extra={"event_id": event.id, "event_type": event.type},
            )
            return
        handler(event)

    def _handle_user_created(self, event: Event) -> None:
        user = event.payload.get("data", {})
        self.logger.info(
            "processed user.created",
            extra={"event_id": event.id, "event_type": event.type},
        )
        # Place business logic here (e.g., create user in DB)
        _ = user

    def _handle_order_created(self, event: Event) -> None:
        order = event.payload.get("data", {})
        # Example: Validate order total
        total = order.get("total", 0)
        if total < 0:
            raise ValueError("invalid order total")
        self.logger.info(
            "processed order.created",
            extra={"event_id": event.id, "event_type": event.type},
        )
        _ = order

    def _handle_echo(self, event: Event) -> None:
        self.logger.info(
            "echo event",
            extra={"event_id": event.id, "event_type": event.type},
        )
        _ = event

