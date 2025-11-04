import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from git_utils import (
    is_git_repo,
    ensure_repo_config,
    init_repo_if_needed,
    get_current_branch,
    has_changes,
    git_add_all,
    git_commit,
    git_push,
    git_pull,
)

logger = logging.getLogger(__name__)


class _DebouncedEventHandler(FileSystemEventHandler):
    def __init__(self, callback, ignore_hidden=True):
        super().__init__()
        self._callback = callback
        self._ignore_hidden = ignore_hidden

    def _should_ignore(self, src_path: str) -> bool:
        # Ignore .git directory and temporary files
        normalized = src_path.replace("\\", "/")
        if "/.git/" in normalized or normalized.endswith("/.git") or "/.git" in normalized:
            return True
        base = os.path.basename(src_path)
        if base == ".git":
            return True
        if base.startswith(".") and self._ignore_hidden:
            # ignore hidden files like .swp or .DS_Store
            return False  # but still allow dotfiles; only .git is ignored
        return False

    def on_any_event(self, event: FileSystemEvent):
        if self._should_ignore(event.src_path):
            return
        self._callback(event)


@dataclass
class DirectoryWatcher:
    id: str
    path: str
    debounce_seconds: float = 2.0
    remote: Optional[str] = None
    branch: Optional[str] = None
    auto_push: bool = True
    auto_init: bool = False

    observer: Observer = field(init=False, default=None)
    _timer: Optional[threading.Timer] = field(init=False, default=None)
    _lock: threading.RLock = field(init=False, default_factory=threading.RLock)
    _paused: bool = field(init=False, default=False)

    last_sync_time: Optional[float] = field(init=False, default=None)
    last_sync_status: Optional[str] = field(init=False, default=None)
    last_sync_details: Optional[Dict[str, Any]] = field(init=False, default=None)

    def __post_init__(self):
        if self.observer is None:
            self.observer = Observer()

    def start(self):
        os.makedirs(self.path, exist_ok=True)
        if self.auto_init:
            init_repo_if_needed(self.path)
        if not is_git_repo(self.path):
            raise RuntimeError(f"Path is not a git repo: {self.path}")
        ensure_repo_config(self.path)
        if not self.branch:
            self.branch = get_current_branch(self.path) or "main"
        handler = _DebouncedEventHandler(self._schedule_sync)
        self.observer.schedule(handler, self.path, recursive=True)
        self.observer.daemon = True
        self.observer.start()
        logger.info("Watcher %s started for %s", self.id, self.path)

    def stop(self):
        with self._lock:
            self._paused = True
            if self._timer:
                self._timer.cancel()
                self._timer = None
        try:
            if self.observer and self.observer.is_alive():
                self.observer.stop()
                self.observer.join(timeout=5)
        except Exception:
            logger.exception("Error stopping observer for %s", self.path)
        logger.info("Watcher %s stopped for %s", self.id, self.path)

    def pause(self):
        with self._lock:
            self._paused = True
            if self._timer:
                self._timer.cancel()
                self._timer = None

    def resume(self):
        with self._lock:
            self._paused = False

    def _schedule_sync(self, _event: FileSystemEvent):
        with self._lock:
            if self._paused:
                return
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self.debounce_seconds, self._perform_sync)
            self._timer.daemon = True
            self._timer.start()

    def _perform_sync(self):
        with self._lock:
            self._timer = None
        try:
            if not has_changes(self.path):
                self._record_sync("no-op", {"message": "No changes to commit"})
                return
            git_add_all(self.path)
            message = f"Auto-sync: {time.strftime('%Y-%m-%d %H:%M:%S')}"
            committed = git_commit(self.path, message)
            details = {"committed": committed}
            if committed and self.auto_push:
                pushed = git_push(self.path, self.remote or "origin", self.branch)
                details["pushed"] = pushed
            self._record_sync("ok", details)
        except Exception as e:
            logger.exception("Sync failed for %s", self.path)
            self._record_sync("error", {"error": str(e)})

    def force_sync(self) -> Dict[str, Any]:
        self._perform_sync()
        return {
            "time": self.last_sync_time,
            "status": self.last_sync_status,
            "details": self.last_sync_details,
        }

    def pull(self) -> Dict[str, Any]:
        out = git_pull(self.path, self.remote or "origin", self.branch or get_current_branch(self.path) or "main")
        self._record_sync("pulled", {"output": out})
        return {"output": out}

    def _record_sync(self, status: str, details: Dict[str, Any]):
        self.last_sync_time = time.time()
        self.last_sync_status = status
        self.last_sync_details = details

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "path": self.path,
            "debounce_seconds": self.debounce_seconds,
            "remote": self.remote or "origin",
            "branch": self.branch,
            "auto_push": self.auto_push,
            "auto_init": self.auto_init,
            "paused": self._paused,
            "last_sync_time": self.last_sync_time,
            "last_sync_status": self.last_sync_status,
            "last_sync_details": self.last_sync_details,
        }