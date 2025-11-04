import threading
import time
from typing import Tuple

# Hybrid Logical Clock: ts string format "ms-counter-node"
# Provides causality while leveraging physical time.

class HLC:
    def __init__(self, node_id: str):
        self.node_id = node_id
        self._lock = threading.Lock()
        self.last_ms = 0
        self.last_counter = 0

    def _now_ms(self) -> int:
        return int(time.time() * 1000)

    def send(self) -> str:
        with self._lock:
            now = self._now_ms()
            if now > self.last_ms:
                self.last_ms = now
                self.last_counter = 0
            else:
                self.last_counter += 1
            return f"{self.last_ms}-{self.last_counter}-{self.node_id}"

    def receive(self, remote_ts: str) -> None:
        r_ms, r_counter, _ = self.parse(remote_ts)
        with self._lock:
            now = self._now_ms()
            new_ms = max(now, self.last_ms, r_ms)
            if new_ms == self.last_ms == r_ms:
                self.last_counter = max(self.last_counter, r_counter) + 1
            elif new_ms == self.last_ms:
                self.last_counter = self.last_counter + 1
            elif new_ms == r_ms:
                self.last_counter = r_counter + 1
            else:
                self.last_counter = 0
            self.last_ms = new_ms

    @staticmethod
    def parse(ts: str) -> Tuple[int, int, str]:
        # format: ms-counter-node
        parts = ts.split("-")
        if len(parts) < 3:
            raise ValueError(f"Invalid HLC ts: {ts}")
        ms = int(parts[0])
        counter = int(parts[1])
        node = "-".join(parts[2:])  # in case node_id contains dashes
        return ms, counter, node

    @staticmethod
    def compare(a: str, b: str) -> int:
        if a == b:
            return 0
        a_ms, a_c, a_node = HLC.parse(a)
        b_ms, b_c, b_node = HLC.parse(b)
        if a_ms < b_ms:
            return -1
        if a_ms > b_ms:
            return 1
        # physical equal, compare counters
        if a_c < b_c:
            return -1
        if a_c > b_c:
            return 1
        # tie-break by node id lexicographically
        if a_node < b_node:
            return -1
        if a_node > b_node:
            return 1
        return 0

