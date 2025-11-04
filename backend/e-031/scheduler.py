import threading
import time
import random
from flask import current_app
from credential_manager import CredentialManager
from models import db


class RotationScheduler:
    def __init__(self, app):
        self.app = app
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, name='RotationScheduler', daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2)

    def _run(self):
        with self.app.app_context():
            mgr = CredentialManager(self.app)
            interval = self.app.config['ROTATION_CHECK_INTERVAL_SECONDS']
            jitter = self.app.config['ROTATION_CHECK_JITTER_SECONDS']
            while not self._stop_event.is_set():
                try:
                    due = mgr.credentials_due_for_rotation()
                    for cred in due:
                        try:
                            mgr.rotate_credential(cred.id, reason='auto-rotation')
                        except Exception as e:
                            # keep going on individual failure
                            pass
                    sleep_for = interval + random.randint(0, max(0, jitter))
                except Exception:
                    sleep_for = interval
                # sleep in small chunks to respond to stop event promptly
                end_time = time.time() + sleep_for
                while time.time() < end_time:
                    if self._stop_event.is_set():
                        return
                    time.sleep(0.5)

