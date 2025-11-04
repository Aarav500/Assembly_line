import os
import time
import uuid


class FileLock:
    def __init__(self, path, timeout=30, poll=0.1):
        self.path = str(path)
        self.timeout = timeout
        self.poll = poll
        self._token = None

    def acquire(self):
        deadline = time.time() + self.timeout
        token = f"pid:{os.getpid()}-{uuid.uuid4().hex}"
        while True:
            try:
                # O_CREAT | O_EXCL ensures atomic creation; fails if exists
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
                with os.fdopen(fd, "w") as f:
                    f.write(token)
                self._token = token
                return True
            except FileExistsError:
                if time.time() > deadline:
                    raise TimeoutError(f"Timeout acquiring lock: {self.path}")
                time.sleep(self.poll)

    def release(self):
        try:
            if os.path.exists(self.path):
                # best-effort: only remove if token matches or file is small
                try:
                    with open(self.path, "r") as f:
                        content = f.read().strip()
                    if not content or content == self._token:
                        os.remove(self.path)
                except Exception:
                    # fallback: try remove
                    try:
                        os.remove(self.path)
                    except Exception:
                        pass
        finally:
            self._token = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()

