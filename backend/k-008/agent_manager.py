from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests
from requests import Response

from utils.backoff import compute_delay


TRANSIENT_HTTP_STATUSES = {408, 425, 429, 500, 502, 503, 504}


class AgentError(Exception):
    pass


class NonRetriableError(AgentError):
    pass


class AllAgentsFailed(AgentError):
    def __init__(self, errors: List[Dict[str, Any]]):
        super().__init__("All agents failed after retries and failover")
        self.errors = errors


@dataclass
class RetryPolicy:
    retries: int
    base: float
    factor: float
    max_delay: float
    jitter: str = "full"  # 'full' | 'equal' | 'none'

    def next_delay(self, attempt: int) -> float:
        return compute_delay(attempt=attempt, base=self.base, factor=self.factor, max_delay=self.max_delay, jitter=self.jitter)


class AgentClient:
    def __init__(self, url: str, timeout: float, logger: Optional[logging.Logger] = None):
        self.url = url
        self.timeout = timeout
        self.session = requests.Session()
        self.log = logger or logging.getLogger(__name__)

    def _is_success(self, resp: Response) -> bool:
        return 200 <= resp.status_code < 300

    def _is_transient_status(self, status_code: int) -> bool:
        return status_code in TRANSIENT_HTTP_STATUSES

    def call_with_retries(self, payload: Dict[str, Any], headers: Optional[Dict[str, str]], retry_policy: RetryPolicy) -> Dict[str, Any]:
        errors: List[Dict[str, Any]] = []
        attempts = 0
        for attempt in range(1, retry_policy.retries + 1):
            attempts = attempt
            try:
                resp = self.session.post(self.url, json=payload, headers=headers, timeout=self.timeout)
            except requests.RequestException as rexc:
                # Treat request exceptions as transient
                delay = retry_policy.next_delay(attempt)
                errors.append({
                    "attempt": attempt,
                    "error": f"network_error: {type(rexc).__name__}: {str(rexc)}",
                    "will_retry": attempt < retry_policy.retries,
                    "delay": delay if attempt < retry_policy.retries else 0,
                })
                if attempt < retry_policy.retries:
                    self.log.warning("Agent %s attempt %d failed with network error: %s. Retrying in %.3fs", self.url, attempt, rexc, delay)
                    time.sleep(delay)
                    continue
                else:
                    break

            # Handle HTTP response
            if self._is_success(resp):
                try:
                    data = resp.json()
                except ValueError:
                    data = {"raw": resp.text}
                return {
                    "response": data,
                    "status_code": resp.status_code,
                    "attempts": attempts,
                    "errors": errors,
                }

            # Not success: decide retry or not
            status = resp.status_code
            body_text = None
            try:
                body_text = json.dumps(resp.json())
            except Exception:
                body_text = resp.text

            if self._is_transient_status(status) and attempt < retry_policy.retries:
                delay = retry_policy.next_delay(attempt)
                errors.append({
                    "attempt": attempt,
                    "status": status,
                    "body": body_text[:512] if body_text else None,
                    "will_retry": True,
                    "delay": delay,
                })
                self.log.warning("Agent %s attempt %d got transient status %s. Retrying in %.3fs", self.url, attempt, status, delay)
                time.sleep(delay)
                continue

            # Non-retriable or out of retries
            errors.append({
                "attempt": attempt,
                "status": status,
                "body": body_text[:512] if body_text else None,
                "will_retry": False,
                "delay": 0,
            })
            break

        raise NonRetriableError(f"Agent {self.url} failed after {attempts} attempts")


class FailoverManager:
    def __init__(
        self,
        agent_urls: List[str],
        request_timeout: float,
        retry_policy: Dict[str, Any],
        logger: Optional[logging.Logger] = None,
    ):
        self.agent_urls = agent_urls
        self.timeout = request_timeout
        self.retry_policy = RetryPolicy(**retry_policy)
        self.log = logger or logging.getLogger(__name__)
        self.clients = [AgentClient(url=u, timeout=request_timeout, logger=self.log) for u in agent_urls]

    def call(self, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        all_errors: List[Dict[str, Any]] = []
        per_agent_attempts: List[int] = []
        for idx, client in enumerate(self.clients):
            try:
                result = client.call_with_retries(payload=payload, headers=headers, retry_policy=self.retry_policy)
                return {
                    "agent_url": client.url,
                    "agent_index": idx,
                    "attempts": sum(per_agent_attempts) + result.get("attempts", 1),
                    "per_agent_attempts": per_agent_attempts + [result.get("attempts", 1)],
                    "response": result.get("response"),
                    "status_code": result.get("status_code"),
                    "errors": all_errors + result.get("errors", []),
                }
            except NonRetriableError as e:
                self.log.error("Agent %s exhausted retries or returned non-retriable error: %s", client.url, e)
                # We already collected per-attempt errors inside the client; we add a summary entry
                per_agent_attempts.append(self.retry_policy.retries)
                all_errors.append({
                    "agent": client.url,
                    "error": str(e),
                })
                continue
            except Exception as e:
                self.log.exception("Unexpected error when calling agent %s", client.url)
                per_agent_attempts.append(1)
                all_errors.append({
                    "agent": client.url,
                    "error": f"unexpected: {type(e).__name__}: {str(e)}",
                })
                continue

        raise AllAgentsFailed(all_errors)

