import logging
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Callable, List, Tuple

logger = logging.getLogger("graceful-cleanup")


class CleanupManager:
    def __init__(self):
        self._hooks: List[Tuple[str, Callable[[], None]]] = []
        self._lock = threading.Lock()

    def register(self, name: str, fn: Callable[[], None]) -> None:
        with self._lock:
            logger.debug("Registered cleanup hook: %s", name)
            self._hooks.append((name, fn))

    def run_all(self, per_hook_timeout: float = 5.0) -> None:
        with self._lock:
            hooks = list(self._hooks)
            # Clear hooks to avoid duplicate runs if called again
            self._hooks.clear()

        if not hooks:
            logger.info("No cleanup hooks to run")
            return

        logger.info("Running %d cleanup hook(s)", len(hooks))
        for name, fn in hooks:
            logger.info("Running cleanup: %s", name)
            try:
                # Run each cleanup in a separate thread to enforce per-hook timeout
                with ThreadPoolExecutor(max_workers=1) as ex:
                    fut = ex.submit(fn)
                    fut.result(timeout=per_hook_timeout)
                logger.info("Completed cleanup: %s", name)
            except TimeoutError:
                logger.warning("Cleanup timed out: %s after %.2fs", name, per_hook_timeout)
            except Exception as e:
                logger.exception("Cleanup failed for %s: %s", name, e)


cleanup_manager = CleanupManager()

