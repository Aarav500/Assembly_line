import logging
import sys
from .masker import Redactor
from .config import Config
from .secrets import SecretStore


class RedactingFormatter(logging.Formatter):
    def __init__(self, fmt: str, datefmt: str | None, redactor: Redactor):
        super().__init__(fmt=fmt, datefmt=datefmt)
        self._redactor = redactor

    def format(self, record: logging.LogRecord) -> str:
        try:
            original = record.getMessage()
            redacted = self._redactor.redact(str(original))
            record.msg = redacted
            record.args = ()
            if record.exc_info:
                # Let base class format exception text, then redact
                s = super().format(record)
                return self._redactor.redact(s)
            return super().format(record)
        finally:
            # No persistent mutation of record beyond this scope that matters
            pass


def setup_logging(app):
    cfg: Config = app.config  # type: ignore
    redactor = Redactor(max_dynamic=cfg.MAX_KNOWN_SECRETS_FOR_REDACTOR)

    # attach redactor to app for later use
    app.extensions = getattr(app, "extensions", {})
    app.extensions["redactor"] = redactor

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(getattr(logging, str(cfg.LOG_LEVEL).upper(), logging.INFO))

    handler = logging.StreamHandler(stream=sys.stdout)
    fmt = "%(asctime)s %(levelname)s %(name)s - %(message)s"
    handler.setFormatter(RedactingFormatter(fmt=fmt, datefmt="%Y-%m-%dT%H:%M:%S%z", redactor=redactor))
    root.addHandler(handler)

    # Flask's own logger inherits root, that's enough

    # Initialize secret store and attach to app
    store = SecretStore(db_path=cfg.SECRETS_DB_PATH, key=cfg.SECRETBOX_KEY, cache_ttl=cfg.SECRET_CACHE_TTL_SECONDS, on_secret_added=redactor.update_known)
    app.extensions["secret_store"] = store

    logging.getLogger(__name__).info("Logging configured with redaction enabled")

