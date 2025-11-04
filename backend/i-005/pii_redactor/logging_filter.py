import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Any


class PiiRedactingFilter(logging.Filter):
    def __init__(self, redactor):
        super().__init__()
        self.redactor = redactor

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.msg, str):
                record.msg = self.redactor.redact_string(record.msg)
            # Redact args if strings or simple containers
            if record.args:
                if isinstance(record.args, tuple):
                    record.args = tuple(self.redactor.redact_string(str(a)) for a in record.args)
                elif isinstance(record.args, dict):
                    record.args = {k: self.redactor.redact_string(str(v)) for k, v in record.args.items()}
        except Exception:
            # Never break logging
            pass
        return True


def configure_logging(app_name: str, log_dir: str, level: str = 'INFO', redactor: Any = None) -> logging.Logger:
    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger(app_name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(getattr(logging, level.upper(), logging.INFO))

    # File handler with rotation
    fh = RotatingFileHandler(os.path.join(log_dir, f"{app_name}.log"), maxBytes=5*1024*1024, backupCount=5)
    fh.setLevel(getattr(logging, level.upper(), logging.INFO))

    fmt = logging.Formatter('%(asctime)s %(levelname)s %(name)s - %(message)s')
    ch.setFormatter(fmt)
    fh.setFormatter(fmt)

    if redactor is not None:
        filt = PiiRedactingFilter(redactor)
        ch.addFilter(filt)
        fh.addFilter(filt)

    # Clear existing handlers if reconfigured
    if logger.handlers:
        for h in list(logger.handlers):
            logger.removeHandler(h)

    logger.addHandler(ch)
    logger.addHandler(fh)
    return logger

