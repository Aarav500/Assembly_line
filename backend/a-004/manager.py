import os
import threading
import uuid
from typing import Dict, List, Optional
from watcher import DirectoryWatcher


class WatcherManager:
    def __init__(self) -> None:
        self._watchers: Dict[str, DirectoryWatcher] = {}
        self._lock = threading.RLock()

    def add_watcher(
        self,
        path: str,
        debounce_seconds: float = 2.0,
        remote: Optional[str] = None,
        branch: Optional[str] = None,
        auto_push: bool = True,
        auto_init: bool = False,
    ) -> DirectoryWatcher:
        try:
            apath = os.path.abspath(os.path.expanduser(path))
            with self._lock:
                # prevent duplicates
                for w in self._watchers.values():
                    try:
                        if os.path.samefile(w.path, apath):
                            return w
                    except (OSError, ValueError):
                        continue
                wid = str(uuid.uuid4())
                watcher = DirectoryWatcher(
                    id=wid,
                    path=apath,
                    debounce_seconds=debounce_seconds,
                    remote=remote,
                    branch=branch,
                    auto_push=auto_push,
                    auto_init=auto_init,
                )
                watcher.start()
                self._watchers[wid] = watcher
                return watcher
        except Exception as e:
            raise RuntimeError(f"Failed to add watcher for path '{path}': {str(e)}") from e

    def remove_watcher(self, watcher_id: str) -> bool:
        try:
            with self._lock:
                w = self._watchers.pop(watcher_id, None)
                if not w:
                    return False
                try:
                    w.stop()
                except Exception:
                    pass
                return True
        except Exception as e:
            raise RuntimeError(f"Failed to remove watcher '{watcher_id}': {str(e)}") from e

    def get_watcher(self, watcher_id: str) -> Optional[DirectoryWatcher]:
        try:
            with self._lock:
                return self._watchers.get(watcher_id)
        except Exception as e:
            raise RuntimeError(f"Failed to get watcher '{watcher_id}': {str(e)}") from e

    def list_watchers(self) -> List[DirectoryWatcher]:
        try:
            with self._lock:
                return list(self._watchers.values())
        except Exception as e:
            raise RuntimeError(f"Failed to list watchers: {str(e)}") from e

    def stop_all(self) -> None:
        try:
            with self._lock:
                for w in list(self._watchers.values()):
                    try:
                        w.stop()
                    except Exception:
                        pass
                self._watchers.clear()
        except Exception as e:
            raise RuntimeError(f"Failed to stop all watchers: {str(e)}") from e