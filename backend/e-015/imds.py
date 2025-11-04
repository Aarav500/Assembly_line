import json
import logging
import threading
import time
from typing import Optional

import requests

logger = logging.getLogger("spot.imds")

IMDS_TOKEN_URL = "http://169.254.169.254/latest/api/token"


class SpotInterruptionWatcher(threading.Thread):
    def __init__(self, lifecycle, poll_interval: float = 5.0, imds_url: str = "http://169.254.169.254/latest/meta-data/spot/instance-action"):
        super().__init__(name="SpotInterruptionWatcher")
        self.lifecycle = lifecycle
        self.poll_interval = poll_interval
        self.imds_url = imds_url
        self._stop = False
        self._token: Optional[str] = None

    def stop(self):
        self._stop = True

    def run(self):
        logger.info("Starting IMDS interruption watcher")
        while not self._stop and not self.lifecycle.is_draining():
            try:
                if self._check_interruption():
                    self.lifecycle.initiate_draining(source="imds")
                    break
            except Exception as e:
                logger.debug("IMDS check error: %s", e)
            time.sleep(self.poll_interval)
        logger.info("IMDS watcher exiting")

    def _get_imds_token(self) -> Optional[str]:
        try:
            r = requests.put(
                IMDS_TOKEN_URL,
                headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
                timeout=0.5,
            )
            if r.status_code == 200:
                return r.text
        except Exception:
            return None
        return None

    def _check_interruption(self) -> bool:
        headers = {"Accept": "application/json, text/plain"}
        if self._token is None:
            self._token = self._get_imds_token()
        if self._token:
            headers["X-aws-ec2-metadata-token"] = self._token
        try:
            r = requests.get(self.imds_url, headers=headers, timeout=0.5)
            # If token invalid or IMDSv2 required, refresh once
            if r.status_code in (401, 403) and self._token is not None:
                self._token = self._get_imds_token()
                headers["X-aws-ec2-metadata-token"] = self._token or ""
                r = requests.get(self.imds_url, headers=headers, timeout=0.5)
        except Exception as e:
            logger.debug("IMDS request failed: %s", e)
            return False

        if r.status_code == 200:
            try:
                data = r.json()
            except ValueError:
                # Sometimes it's plain text; still treat as interruption
                data = {"raw": r.text}
            logger.warning("Spot interruption notice received: %s", json.dumps(data))
            return True
        elif r.status_code == 404:
            # No interruption scheduled
            return False
        else:
            logger.debug("IMDS response status: %s", r.status_code)
            return False

