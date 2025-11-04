from __future__ import annotations
import re
import threading
from typing import Iterable, List


def _compile_patterns() -> List[re.Pattern]:
    patterns = [
        # Key-value like token: password: xxx, token=xxx, secret: "xxx"
        re.compile(r"(?i)(password|token|secret|api[-_ ]?key)\s*[:=]\s*([^\s'\"]+)", re.MULTILINE),
        # Bearer token
        re.compile(r"(?i)bearer\s+([A-Za-z0-9\-\._~\+\/]+=*)"),
        # AWS Access Key ID
        re.compile(r"(AKIA|ASIA)[0-9A-Z]{16}"),
        # AWS Secret Access Key (heuristic)
        re.compile(r"(?i)aws.{0,16}(secret|sk|secret_access_key).{0,3}([A-Za-z0-9\/=\+]{40})"),
        # JWT
        re.compile(r"eyJ[\w-]+\.[\w-]+\.[\w-]+"),
        # Private key blocks (single-line or multi-line)
        re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
        # Basic auth in URL
        re.compile(r"https?:\/\/[^\s:@\/]+:[^\s@\/]+@[^\s]+"),
    ]
    return patterns


class Redactor:
    def __init__(self, max_dynamic: int = 1000):
        self._patterns = _compile_patterns()
        self._dynamic_values: List[str] = []
        self._dynamic_re: re.Pattern | None = None
        self._lock = threading.RLock()
        self._max_dynamic = max_dynamic

    def update_known(self, value: str):
        if not value:
            return
        with self._lock:
            # keep up to max_dynamic recent values
            self._dynamic_values.append(value)
            if len(self._dynamic_values) > self._max_dynamic:
                self._dynamic_values = self._dynamic_values[-self._max_dynamic :]
            self._rebuild_dynamic()

    def set_known_many(self, values: Iterable[str]):
        with self._lock:
            self._dynamic_values = [v for v in values if v][: self._max_dynamic]
            self._rebuild_dynamic()

    def _rebuild_dynamic(self):
        if not self._dynamic_values:
            self._dynamic_re = None
            return
        escaped = [re.escape(v) for v in self._dynamic_values if v]
        # Avoid overly large patterns
        escaped = escaped[: self._max_dynamic]
        try:
            self._dynamic_re = re.compile("(" + "|".join(escaped) + ")")
        except Exception:
            self._dynamic_re = None

    @staticmethod
    def _mask(s: str) -> str:
        if s is None:
            return "***"
        return "***"

    def redact(self, text: str, extra_values: Iterable[str] | None = None) -> str:
        if not text:
            return text
        redacted = text
        # Apply known patterns
        for pat in self._patterns:
            try:
                if pat.groups:
                    redacted = pat.sub(lambda m: m.group(0).replace(m.group(m.lastindex or 1), self._mask(m.group(m.lastindex or 1))), redacted)
                else:
                    redacted = pat.sub(self._mask("X"), redacted)
            except Exception:
                continue
        # Apply dynamic known secrets
        with self._lock:
            dyn = self._dynamic_re
        if dyn is not None:
            try:
                redacted = dyn.sub(self._mask("X"), redacted)
            except Exception:
                pass
        # Apply ad-hoc extra values
        if extra_values:
            for v in extra_values:
                if not v:
                    continue
                try:
                    redacted = re.sub(re.escape(v), self._mask(v), redacted)
                except Exception:
                    pass
        return redacted

